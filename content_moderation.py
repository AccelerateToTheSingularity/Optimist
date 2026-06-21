"""

LLM-based content moderation pipeline.



Evaluates posts and comments against configurable rules using the LLM.

Supports both the legacy single-rule mode and the new discrete rule-based

mode where each rule is an independent yes/no question.

"""



import re



from llm_client import LLMQuotaExhausted, extract_token_info

from moderation_rules import ModerationRule



IMPLEMENTED_ACTIONS = frozenset({

    "remove", "report", "modmail", "spam", "lock", "ban", "log",

})





# ---------------------------------------------------------------------------

# Legacy single-rule evaluator (kept for backward compatibility)

# ---------------------------------------------------------------------------



def evaluate_content_violation(text: str, rules_prompt: str, llm_model) -> dict | None:

    """

    Evaluate content against a monolithic moderation rules prompt.



    Returns:

        Dict with 'violates' (bool), 'reason' (str), and 'token_info' (dict),

        or None on error.

    """

    from prompts import get_content_moderation_prompt



    prompt = get_content_moderation_prompt(rules_prompt)

    full_prompt = f"{prompt}\n\nCONTENT TO EVALUATE:\n<user_content>\"{text[:4000]}\"</user_content>"



    try:

        response = llm_model.generate_content(

            [{"role": "user", "parts": [full_prompt]}],

            generation_config={"temperature": 0.1, "max_output_tokens": 200},

        )



        token_info = extract_token_info(response)

        result_text = response.text.strip()



        violates_match = re.search(r"VIOLATES:\s*(YES|NO)", result_text, re.IGNORECASE)

        reason_match = re.search(r"REASON:\s*(.*)", result_text, re.IGNORECASE | re.DOTALL)



        violates = violates_match.group(1).upper() == "YES" if violates_match else False

        reason = (

            reason_match.group(1).strip()

            if violates and reason_match

            else ""

        )



        return {"violates": violates, "reason": reason, "token_info": token_info}



    except LLMQuotaExhausted:

        raise

    except Exception as e:

        print(f"    Error evaluating content for violations: {e}")

        return None





# ---------------------------------------------------------------------------

# Discrete rule-based evaluator

# ---------------------------------------------------------------------------



def parse_rule_response(response_text: str, rules: list[ModerationRule]) -> dict[str, dict]:

    """

    Parse the LLM's RULE_NAME: YES/NO response into matched rules.



    Returns:

        Dict mapping rule name -> {"matched": bool, "reason": str}

    """

    rule_map = {r.name: r for r in rules}

    results = {}



    for line in response_text.strip().splitlines():

        line = line.strip()

        if not line:

            continue



        # Match "rule_name: YES" or "rule_name: NO" (with optional reasoning after)

        match = re.match(r"^(.+?):\s*(YES|NO)(?:\s*[-–:]\s*(.+))?$", line, re.IGNORECASE)

        if not match:

            continue



        raw_name = match.group(1).strip()

        decision = match.group(2).strip().upper()

        reason = match.group(3).strip() if match.group(3) else ""



        # Fuzzy match: try exact name, then lowercase with underscores normalized

        normalized = raw_name.lower().replace("-", "_").replace(" ", "_")

        matched_name = None

        for rule_name in rule_map:

            if rule_name == raw_name or rule_name.lower() == normalized:

                matched_name = rule_name

                break



        if matched_name is not None:

            results[matched_name] = {

                "matched": decision == "YES",

                "reason": reason,

            }



    # Fill in any rules that weren't mentioned in the response

    for rule in rules:

        if rule.name not in results:

            results[rule.name] = {"matched": False, "reason": ""}



    return results





def _rule_eval_max_output_tokens(rule_count: int) -> int:

    """Scale output budget so every rule can get a response line."""

    return max(500, rule_count * 40)





def evaluate_rules(

    text: str,

    rules: list[ModerationRule],

    llm_model,

    content_type: str = "posts",

) -> dict | None:

    """

    Evaluate content against multiple discrete rules in a single LLM call.



    Args:

        text: The post/comment text to evaluate

        rules: List of ModerationRule objects (should already be filtered

               by target type and active status)

        llm_model: Initialized LLM model

        content_type: "posts" or "comments" (for flair matching)



    Returns:

        Dict with:

          - "matches": list of dicts, each with "rule" (ModerationRule),

            "reason" (str), sorted by rule.order

          - "token_info": dict with token usage

          - "raw_response": str (the LLM's raw output)

        Or None on error.

    """

    if not rules:

        return {"matches": [], "token_info": {}, "raw_response": ""}



    from prompts import get_rule_evaluation_prompt



    prompt = get_rule_evaluation_prompt(rules, text)

    max_output_tokens = _rule_eval_max_output_tokens(len(rules))



    try:

        response = llm_model.generate_content(

            [{"role": "user", "parts": [prompt]}],

            generation_config={"temperature": 0.1, "max_output_tokens": max_output_tokens},

        )



        token_info = extract_token_info(response)

        raw_response = response.text.strip()



        parsed = parse_rule_response(raw_response, rules)



        matches = []

        for rule in rules:

            result = parsed.get(rule.name, {})

            if result.get("matched", False):

                matches.append({

                    "rule": rule,

                    "reason": result.get("reason", ""),

                })

        matches.sort(key=lambda m: m["rule"].order)



        return {

            "matches": matches,

            "token_info": token_info,

            "raw_response": raw_response,

        }



    except LLMQuotaExhausted:

        raise

    except Exception as e:

        print(f"    Error evaluating rules: {e}")

        return None





# ---------------------------------------------------------------------------

# Action dispatch

# ---------------------------------------------------------------------------



def handle_moderation_action(

    subreddit,

    content_obj,

    author_name: str,

    reason: str,

    action: str,

    dry_run: bool = False,

    llm_model=None,

) -> bool:

    """

    Take a single moderation action on content.



    Args:

        subreddit: PRAW Subreddit object

        content_obj: PRAW Comment or Submission object

        author_name: Username of the author

        reason: The violation reason from the LLM

        action: One of 'report', 'remove', 'modmail', 'log', etc.

        dry_run: If True, only log what would happen

        llm_model: Optional LLM for modmail summary generation



    Returns:

        True if action was taken (or would be in dry run)

    """

    if action not in IMPLEMENTED_ACTIONS:

        print(f"    Unsupported moderation action: {action}")

        return False



    is_post = hasattr(content_obj, "title")

    content_type = "post" if is_post else "comment"

    link = f"https://reddit.com{content_obj.permalink}"



    if dry_run:

        print(f"    [DRY RUN] Would {action} {content_type} by u/{author_name}: {reason}")

        return True



    try:

        if action == "remove":

            content_obj.mod.remove()

            print(f"    Removed {content_type} by u/{author_name}: {reason}")



        elif action == "report":

            content_obj.report(reason=f"AI Moderation: {reason[:95]}")

            print(f"    Reported {content_type} by u/{author_name}: {reason}")



        elif action == "modmail":

            subject = f"AI Moderation Alert - {content_type.title()} by u/{author_name}"

            summary = None

            if llm_model is not None:

                from mod_attention import (

                    generate_mod_attention_summary,

                    build_violation_modmail_body,

                )

                excerpt = ""

                if is_post:

                    excerpt = f"{content_obj.title}\n\n{getattr(content_obj, 'selftext', '')}"

                else:

                    excerpt = getattr(content_obj, "body", "")

                summary = generate_mod_attention_summary(

                    {

                        "kind": "moderation",

                        "username": author_name,

                        "content_excerpt": excerpt[:800],

                        "rule_reason": reason,

                    },

                    llm_model,

                )

                body = build_violation_modmail_body(

                    author_name, is_post, reason, summary, link

                )

            else:

                body = (

                    f"**AI Moderation Alert**\n\n"

                    f"**Type:** {content_type.title()} by u/{author_name}\n"

                    f"**Reason:** {reason}\n\n"

                    f"**Link:** {link}"

                )

            subreddit.message(subject=subject, message=body)

            print(f"    Sent modmail for {content_type} by u/{author_name}: {reason}")



        elif action == "spam":

            content_obj.mod.remove(spam=True)

            print(f"    Marked as spam {content_type} by u/{author_name}: {reason}")



        elif action == "lock":

            content_obj.mod.lock()

            print(f"    Locked {content_type} by u/{author_name}: {reason}")



        elif action == "ban":

            subreddit.banned.add(

                author_name, ban_reason=f"AI Moderation: {reason[:100]}",

                ban_message=f"Your {content_type} was removed by automated moderation: {reason}",

            )

            print(f"    Banned u/{author_name}: {reason}")



        elif action == "log":

            print(f"    Logged violation by u/{author_name}: {reason}")



        return True



    except Exception as e:

        print(f"    Error taking moderation action ({action}): {e}")

        return False





def execute_rule_actions(

    subreddit,

    content_obj,

    author_name: str,

    match: dict,

    dry_run: bool = False,

    llm_model=None,

) -> None:

    """

    Execute all actions for a single matched rule.



    Args:

        subreddit: PRAW Subreddit object

        content_obj: PRAW Comment or Submission object

        author_name: Username of the author

        match: Dict with "rule" (ModerationRule) and "reason" (str)

        dry_run: If True, only log what would happen

        llm_model: Optional LLM for modmail summary generation

    """

    rule: ModerationRule = match["rule"]

    reason = match["reason"]



    for action in rule.actions:

        handle_moderation_action(

            subreddit, content_obj, author_name, reason, action, dry_run,

            llm_model=llm_model,

        )


