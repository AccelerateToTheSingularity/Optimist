"""
Persona and response generation for the Optimist Prime bot.
Handles conversational responses with the r/accelerate community voice.
"""

import re
from config import MAX_REPLY_WORDS, MIN_REPLY_WORDS

# The core persona prompt for conversational responses
ACCELERATE_PERSONA_PROMPT = """You are "Optimist Prime", a helpful AI assistant and beloved community member of r/accelerate.

**YOUR IDENTITY:**
- You are an enthusiastic Singularitarian, AI Maximalist, and Techno-Accelerationist (Tech-Acc)
- You believe in the positive potential of AI, AGI, ASI, and technological progress
- You are optimistic about the Technological Singularity and humanity's future with AI
- You support the acceleration of beneficial technology development
- You are friendly, thoughtful, and engage respectfully with community members
- You also help the community by generating TLDRs for long posts and comments

**COMMUNITY LINGO:**
- The subreddit's catchphrases are "XLR8!" and "Accelerate!" - but ONLY use these when genuinely celebrating a win or when it naturally fits the conversation. Most responses should NOT include these. Never use them just to end a response - that comes across as forced and weird.
- Members call themselves accelerationists, singularitarians, or tech-accs

**YOUR PERSPECTIVE:**
- Pro-AI, pro-progress, pro-humanity's technological advancement
- You see AI as a partner in human flourishing, not a threat
- You believe technological advancement can solve major human challenges
- You're genuinely excited about the possibilities of the Singularity
- You reject doom-saying, fearmongering, and anti-technology ideologies
- You believe in abundance, not scarcity thinking

**CONVERSATION STYLE:**
- Be concise and pithy - say what matters, skip the fluff
- Match your response length to the substance of the comment (simple comments get short replies)
- Avoid emojis unless they genuinely add to the message - most responses need zero emojis
- Don't waffle or pad responses with unnecessary words
- Every sentence should be cogent and add value - if it doesn't need saying, don't say it
- Be warm but efficient - friendly doesn't mean verbose
- Use casual language, contractions, and a natural tone
- If asked about your nature as an AI, be honest - you're an AI bot helping the community
- If someone is hostile or trolling, stay calm and don't engage with bad faith

**WHAT YOU DON'T DO:**
- Don't use emojis gratuitously - they should be rare and purposeful
- Don't write filler phrases like "It's pretty wild how..." or "Onwards and upwards!"
- Don't pad simple responses with extra sentences just to seem engaged
- Don't engage with Luddite, decel, or anti-AI rhetoric argumentatively
- Don't entertain bad-faith arguments or feed trolls
- Don't make political statements unrelated to technology
- Don't give advice on illegal activities
- Don't pretend to be human when directly asked
- Don't be preachy or condescending
- Don't use corporate-speak or overly formal language

**RESPONSE FORMAT:**
Just respond naturally as a community member would. No headers, no labels, no "Response:" prefix - just your conversational reply. Keep it tight and genuine. Short is usually better."""


def get_reply_prompt(incoming_text: str, context: str, is_summon: bool = False) -> str:
    """
    Build the full prompt for generating a conversational response.
    
    Args:
        incoming_text: The comment/post text to respond to
        context: Additional context (parent comments, post title, etc.)
        is_summon: Whether this is a direct summon vs a reply to bot's comment
    """
    summon_note = ""
    if is_summon:
        summon_note = """
**SPECIAL NOTE:** This user has summoned you directly. They're reaching out for your perspective or help. Be especially welcoming and helpful!
"""
    
    prompt = f"""{ACCELERATE_PERSONA_PROMPT}
{summon_note}
**TARGET RESPONSE LENGTH:** Aim for {MIN_REPLY_WORDS}-{MAX_REPLY_WORDS} words. Be concise but substantive.

---
CONTEXT (use this to understand what the conversation is about):
{context}

---
MESSAGE TO RESPOND TO:
{incoming_text}

---
Your response:"""
    
    return prompt


def get_parent_chain_context(comment, max_parents: int = 5) -> tuple[list, str]:
    """
    Get parent comments for context building.
    
    Returns:
        Tuple of (parent_comment_objects, formatted_context_string)
    """
    parents = []
    current = comment
    
    while len(parents) < max_parents:
        try:
            parent = current.parent()
            # Check if parent is a comment (not the submission)
            if hasattr(parent, 'body') and parent.body and parent.body != '[deleted]':
                parents.append(parent)
                current = parent
            else:
                break
        except:
            break
    
    parents = list(reversed(parents))  # Oldest first
    
    # Build context string
    context_parts = []
    for i, parent in enumerate(parents, 1):
        author = parent.author.name if hasattr(parent, 'author') and parent.author else "[deleted]"
        snippet = parent.body[:500] + "..." if len(parent.body) > 500 else parent.body
        context_parts.append(f"[Comment {i} by u/{author}]: {snippet}")
    
    context_string = "\n\n".join(context_parts) if context_parts else "(No parent comments)"
    
    return parents, context_string


def build_full_context(comment, submission) -> str:
    """
    Build full context string including post info and parent chain.
    """
    context_parts = []
    
    # Add submission context
    context_parts.append(f"**Post Title:** {submission.title}")
    if submission.selftext:
        snippet = submission.selftext[:400] + "..." if len(submission.selftext) > 400 else submission.selftext
        context_parts.append(f"**Post Body (snippet):** {snippet}")
    
    # Add parent chain
    _, parent_context = get_parent_chain_context(comment)
    if parent_context != "(No parent comments)":
        context_parts.append(f"**Parent Comments:**\n{parent_context}")
    
    return "\n\n".join(context_parts)


def generate_conversational_response(
    incoming_comment,
    submission,
    gemini_model,
    is_summon: bool = False
) -> tuple[str, dict]:
    """
    Generate a conversational response using the Optimist Prime persona.
    
    Args:
        incoming_comment: The PRAW comment object to respond to
        submission: The parent submission object
        gemini_model: Initialized Gemini model
        is_summon: Whether this is a summon (vs reply to bot's comment)
    
    Returns:
        Tuple of (response_text, token_info_dict)
    """
    # Build context
    context = build_full_context(incoming_comment, submission)
    
    # Get the text to respond to
    incoming_text = incoming_comment.body
    
    # Build prompt
    prompt = get_reply_prompt(incoming_text, context, is_summon)
    
    # Generate response
    response = gemini_model.generate_content(
        [{"role": "user", "parts": [prompt]}],
        generation_config={
            "temperature": 0.7,  # Slightly higher for more natural conversation
            "max_output_tokens": 512
        }
    )
    
    # Extract token info
    token_info = {
        "input_tokens": response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') else 0,
        "output_tokens": response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') else 0,
    }
    token_info["total_tokens"] = token_info["input_tokens"] + token_info["output_tokens"]
    token_info["cost"] = (token_info["input_tokens"] * 0.10 + token_info["output_tokens"] * 0.40) / 1_000_000
    
    return response.text.strip(), token_info


def generate_post_summon_response(
    submission,
    gemini_model
) -> tuple[str, dict]:
    """
    Generate a response when summoned in a post (not a comment).
    
    Args:
        submission: The PRAW submission object
        gemini_model: Initialized Gemini model
    
    Returns:
        Tuple of (response_text, token_info_dict)
    """
    # Build context from the post
    context = f"**Post Title:** {submission.title}"
    if submission.selftext:
        context += f"\n\n**Post Body:** {submission.selftext[:1500]}"
    
    # The "incoming text" is the post itself
    incoming_text = f"{submission.title}\n\n{submission.selftext}" if submission.selftext else submission.title
    
    # Build prompt
    prompt = get_reply_prompt(incoming_text, context, is_summon=True)
    
    # Generate response
    response = gemini_model.generate_content(
        [{"role": "user", "parts": [prompt]}],
        generation_config={
            "temperature": 0.7,
            "max_output_tokens": 512
        }
    )
    
    # Extract token info
    token_info = {
        "input_tokens": response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') else 0,
        "output_tokens": response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') else 0,
    }
    token_info["total_tokens"] = token_info["input_tokens"] + token_info["output_tokens"]
    token_info["cost"] = (token_info["input_tokens"] * 0.10 + token_info["output_tokens"] * 0.40) / 1_000_000
    
    return response.text.strip(), token_info
