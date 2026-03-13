"""
UTM-трекинг и воронка конверсии для VYUD AI.
Используется в app.py (веб), bot.py (Telegram), лендинге.

Автор: Claude Sonnet 4.5
Дата: 2026-03-05
"""

import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any

try:
    from supabase import create_client
    
    # Initialize Supabase client
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    
    if SUPABASE_URL and SUPABASE_KEY:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    else:
        supabase = None
        logging.warning("⚠️  Supabase credentials not found in environment")
except Exception as e:
    supabase = None
    logging.error(f"❌ Failed to initialize Supabase client: {e}")


# Conversion Funnel Steps (in order)
FUNNEL_STEPS = [
    "visit",              # Visited site/bot
    "signup",             # Registered (users_credits created)
    "first_generation",   # First test generation
    "second_generation",  # Second generation (engagement)
    "payment",            # Payment made
    "repeat",             # Repeat payment
    "scorm_export"        # Exported SCORM (enterprise signal)
]


def track_event(
    funnel_step: str,
    telegram_id: Optional[int] = None,
    email: Optional[str] = None,
    utm_source: Optional[str] = None,
    utm_medium: Optional[str] = None,
    utm_campaign: Optional[str] = None,
    utm_content: Optional[str] = None,
    utm_term: Optional[str] = None,
    source_platform: Optional[str] = None,
    page_url: Optional[str] = None,
    session_id: Optional[str] = None,
    user_agent: Optional[str] = None,
    referrer: Optional[str] = None
) -> bool:
    """
    Records funnel event to utm_events table.
    
    Args:
        funnel_step: One of FUNNEL_STEPS
        telegram_id: Telegram user ID
        email: User email
        utm_source: UTM source (telegram, vk, youtube, google, direct)
        utm_medium: UTM medium (cpc, social, video, organic, bot)
        utm_campaign: Campaign name
        utm_content: Ad variant (A/B test)
        utm_term: Keyword
        source_platform: Platform (web, telegram_bot, landing)
        page_url: Page URL
        session_id: Session identifier
        user_agent: User agent string
        referrer: HTTP referrer
    
    Returns:
        bool: True if successful, False otherwise
    """
    if not supabase:
        logging.warning("⚠️  Supabase not initialized, skipping UTM tracking")
        return False
    
    if funnel_step not in FUNNEL_STEPS:
        logging.warning(f"⚠️  Invalid funnel_step: {funnel_step}. Valid: {FUNNEL_STEPS}")
    
    try:
        data = {
            "funnel_step": funnel_step,
            "telegram_id": telegram_id,
            "email": email,
            "utm_source": utm_source,
            "utm_medium": utm_medium,
            "utm_campaign": utm_campaign,
            "utm_content": utm_content,
            "utm_term": utm_term,
            "source_platform": source_platform,
            "page_url": page_url,
            "session_id": session_id,
            "user_agent": user_agent,
            "referrer": referrer
        }
        
        # Remove None values to keep DB clean
        data = {k: v for k, v in data.items() if v is not None}
        
        # Insert event
        supabase.table("utm_events").insert(data).execute()
        
        logging.info(f"📊 UTM Event: {funnel_step} | {telegram_id or email} | {utm_source or 'direct'}/{utm_medium or 'organic'}")
        return True
        
    except Exception as e:
        logging.error(f"❌ UTM tracking error: {e}")
        return False


def parse_utm_from_start_param(start_param: Optional[str]) -> Dict[str, Optional[str]]:
    """
    Parses UTM from Telegram bot /start parameter.
    
    Deeplink format: /start utm_SOURCE_MEDIUM_CAMPAIGN_CONTENT_TERM
    
    Examples:
      /start utm_telegram_cpc_spring25_variantA
      /start utm_vk_social_test1
      /start utm_youtube_video_review
      /start ref_PARTNER (referral, not UTM - returns empty dict)
    
    Args:
        start_param: Start parameter from /start command
    
    Returns:
        dict: UTM parameters (empty values if not found)
    """
    result = {
        "utm_source": None,
        "utm_medium": None,
        "utm_campaign": None,
        "utm_content": None,
        "utm_term": None
    }
    
    if not start_param or not isinstance(start_param, str):
        return result
    
    # Check if it's a UTM parameter
    if not start_param.startswith("utm_"):
        return result
    
    # Split by underscore and parse
    parts = start_param.split("_")[1:]  # Remove "utm" prefix
    
    if len(parts) >= 1: result["utm_source"] = parts[0]
    if len(parts) >= 2: result["utm_medium"] = parts[1]
    if len(parts) >= 3: result["utm_campaign"] = parts[2]
    if len(parts) >= 4: result["utm_content"] = parts[3]
    if len(parts) >= 5: result["utm_term"] = parts[4]
    
    return result


def parse_utm_from_url_params(params: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """
    Parses UTM from URL query parameters (for Streamlit st.query_params).
    
    Args:
        params: Query parameters dict from st.query_params
    
    Returns:
        dict: UTM parameters
    """
    def get_param(key: str) -> Optional[str]:
        value = params.get(key)
        if value is None:
            return None
        # Handle both list and string formats
        if isinstance(value, list):
            return value[0] if value else None
        return str(value)
    
    return {
        "utm_source": get_param("utm_source"),
        "utm_medium": get_param("utm_medium"),
        "utm_campaign": get_param("utm_campaign"),
        "utm_content": get_param("utm_content"),
        "utm_term": get_param("utm_term"),
    }


def get_user_utm(telegram_id: Optional[int] = None, email: Optional[str] = None) -> Dict[str, Any]:
    """
    Gets first UTM parameters for a user (first touch attribution).
    
    Args:
        telegram_id: Telegram user ID
        email: User email
    
    Returns:
        dict: First UTM parameters for the user (empty if not found)
    """
    if not supabase:
        return {}
    
    try:
        query = supabase.table("utm_events").select("utm_source, utm_medium, utm_campaign, utm_content, utm_term, created_at")
        
        if telegram_id:
            query = query.eq("telegram_id", telegram_id)
        elif email:
            query = query.eq("email", email)
        else:
            return {}
        
        # Get first "visit" event (first touch)
        result = query.eq("funnel_step", "visit").order("created_at").limit(1).execute()
        
        if result.data:
            return result.data[0]
        
        return {}
        
    except Exception as e:
        logging.error(f"❌ Error getting user UTM: {e}")
        return {}


def get_funnel_stats(days: int = 30) -> Dict[str, Any]:
    """
    Gets conversion funnel statistics for the last N days.
    
    Args:
        days: Number of days to look back
    
    Returns:
        dict: Funnel statistics with counts for each step
    """
    if not supabase:
        return {}
    
    try:
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)
        
        stats = {}
        
        for step in FUNNEL_STEPS:
            # Count unique users at this step
            result = supabase.table("utm_events") \
                .select("telegram_id, email", count="exact") \
                .eq("funnel_step", step) \
                .gte("created_at", cutoff.isoformat()) \
                .execute()
            
            stats[step] = result.count if hasattr(result, 'count') else len(result.data)
        
        return stats
        
    except Exception as e:
        logging.error(f"❌ Error getting funnel stats: {e}")
        return {}


def get_source_stats(days: int = 30) -> Dict[str, Dict[str, int]]:
    """
    Gets traffic source statistics for the last N days.
    
    Args:
        days: Number of days to look back
    
    Returns:
        dict: Source statistics with breakdown by funnel step
    """
    if not supabase:
        return {}
    
    try:
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)
        
        result = supabase.table("utm_events") \
            .select("utm_source, funnel_step") \
            .gte("created_at", cutoff.isoformat()) \
            .execute()
        
        # Group by source and funnel step
        stats = {}
        for event in result.data:
            source = event.get("utm_source", "direct")
            step = event.get("funnel_step")
            
            if source not in stats:
                stats[source] = {}
            
            if step not in stats[source]:
                stats[source][step] = 0
            
            stats[source][step] += 1
        
        return stats
        
    except Exception as e:
        logging.error(f"❌ Error getting source stats: {e}")
        return {}


# Export public API
__all__ = [
    'FUNNEL_STEPS',
    'track_event',
    'parse_utm_from_start_param',
    'parse_utm_from_url_params',
    'get_user_utm',
    'get_funnel_stats',
    'get_source_stats'
]
