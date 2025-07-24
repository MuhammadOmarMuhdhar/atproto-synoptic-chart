import os
import re
from datetime import datetime
from typing import List, Dict, Any
from dotenv import load_dotenv
from atproto import Client as AtProtoClient
from langdetect import detect, DetectorFactory

# Set seed for consistent results
DetectorFactory.seed = 0

load_dotenv()

class Client:
    def __init__(self):
        self.client = AtProtoClient()
        self.handle = os.getenv('BLUESKY_USERNAME')
        self.password = os.getenv('BLUESKY_PASSWORD')
        self.posts = []
        
    def authenticate(self):
        """Authenticate with Bluesky"""
        try:
            self.client.login(self.handle, self.password)
            print(f"Successfully authenticated as {self.handle}")
            return True
        except Exception as e:
            print(f"Authentication failed: {e}")
            return False
    
    def remove_emojis(self, text: str) -> str:
        """Remove emojis from text"""
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags (iOS)
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE)
        return emoji_pattern.sub(r'', text)

    def is_english(self, text: str) -> bool:
        """Robust English detection using langdetect"""
        clean_text = self.remove_emojis(text).strip()
        
        if not clean_text or len(clean_text) < 20:
            return False
        
        try:
            detected_lang = detect(clean_text)
            return detected_lang == 'en'
        except:
            # Fallback to simple detection if langdetect fails
            return self._simple_english_detection(clean_text)
    
    def _simple_english_detection(self, text: str) -> bool:
        """Fallback simple English detection"""
        text_lower = text.lower()
        english_indicators = ['the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'its', 'may', 'new', 'now', 'old', 'see', 'two', 'who', 'boy', 'did', 'has', 'let', 'put', 'say', 'she', 'too', 'use']
        english_word_count = sum(1 for word in english_indicators if word in text_lower)
        
        # Check for Spanish indicators
        spanish_words = ['que', 'del', 'los', 'las', 'para', 'con', 'más', 'pero', 'qué', 'está']
        spanish_count = sum(1 for word in spanish_words if word in text_lower)
        
        # Check for Spanish accents
        spanish_chars = re.findall(r'[áéíóúüñ¿¡]', text_lower)
        
        # Reject if Spanish indicators
        if spanish_count >= 2 or len(spanish_chars) >= 1:
            return False
        
        return english_word_count >= 2


    def fetch_popular_posts(self, limit: int = 100, min_length: int = 50) -> List[Dict[str, Any]]:
        """Fetch popular posts from Hot Classic feed - trending posts across Bluesky"""
        posts = []
        try:
            # Use Hot Classic feed - curated trending/popular posts
            hot_classic_feed = "at://did:plc:z72i7hdynmk6r22z27h6tvur/app.bsky.feed.generator/hot-classic"
            from atproto import models
            response = self.client.app.bsky.feed.get_feed(
                models.AppBskyFeedGetFeed.Params(feed=hot_classic_feed, limit=limit)
            )
            
            for post in response.feed:
                if post.post.record.text:
                    text = post.post.record.text
                    
                    # Check if post has language metadata (most reliable)
                    post_langs = getattr(post.post.record, 'langs', [])
                    is_english_by_api = any(lang.startswith('en') for lang in post_langs) if post_langs else None
                    
                    # Filter: English (by API or fallback detection), minimum length, not just URLs/mentions
                    is_english_post = (
                        is_english_by_api if is_english_by_api is not None 
                        else self.is_english(text)
                    )
                    
                    if (len(text) >= min_length and 
                        is_english_post and
                        not re.match(r'^[@#\s]*$', text)):  # Not just mentions/hashtags
                        
                        clean_text = self.remove_emojis(text).strip()
                        
                        # Only save if the cleaned text is meaningful (not empty after cleaning)
                        if clean_text and len(clean_text) >= min_length:
                            engagement_score = (
                                (post.post.like_count or 0) + 
                                (post.post.repost_count or 0) + 
                                (post.post.reply_count or 0)
                            )
                            
                            post_data = {
                                'uri': post.post.uri,
                                'text': clean_text,
                                'author': post.post.author.handle,
                                'created_at': post.post.record.created_at,
                                'like_count': post.post.like_count or 0,
                                'repost_count': post.post.repost_count or 0,
                                'reply_count': post.post.reply_count or 0,
                                'engagement_score': engagement_score,
                                'text_length': len(clean_text),
                                'fetched_at': datetime.now().isoformat(),
                                'source': 'hot_classic_feed'
                            }
                            posts.append(post_data)
            
            self.posts = posts
            print(f"Fetched {len(posts)} trending English posts from Hot Classic feed (min {min_length} chars)")
            return posts
            
        except Exception as e:
            print(f"Error fetching Hot Classic feed: {e}")
            return []
    
    def get_posts_data(self) -> List[Dict[str, Any]]:
        """Return the stored posts data"""
        return self.posts
    
    def get_top_posts(self, n: int = 10) -> List[Dict[str, Any]]:
        """Get top N most popular posts"""
        return self.posts[:n]
    
    def fetch_from_custom_feed(self, feed_uri: str, limit: int = 100, min_length: int = 50) -> List[Dict[str, Any]]:
        """Fetch posts from any custom feed URI"""
        posts = []
        try:
            from atproto import models
            response = self.client.app.bsky.feed.get_feed(
                models.AppBskyFeedGetFeed.Params(feed=feed_uri, limit=limit)
            )
            
            for post in response.feed:
                if post.post.record.text:
                    text = post.post.record.text
                    
                    # Check if post has language metadata (most reliable)
                    post_langs = getattr(post.post.record, 'langs', [])
                    is_english_by_api = any(lang.startswith('en') for lang in post_langs) if post_langs else None
                    
                    # Filter: English (by API or fallback detection), minimum length, not just URLs/mentions
                    is_english_post = (
                        is_english_by_api if is_english_by_api is not None 
                        else self.is_english(text)
                    )
                    
                    if (len(text) >= min_length and 
                        is_english_post and
                        not re.match(r'^[@#\s]*$', text)):
                        
                        clean_text = self.remove_emojis(text).strip()
                        
                        # Only save if the cleaned text is meaningful (not empty after cleaning)
                        if clean_text and len(clean_text) >= min_length:
                            engagement_score = (
                                (post.post.like_count or 0) + 
                                (post.post.repost_count or 0) + 
                                (post.post.reply_count or 0)
                            )
                            
                            post_data = {
                                'uri': post.post.uri,
                                'text': clean_text,
                                'author': post.post.author.handle,
                                'created_at': post.post.record.created_at,
                                'like_count': post.post.like_count or 0,
                                'repost_count': post.post.repost_count or 0,
                                'reply_count': post.post.reply_count or 0,
                                'engagement_score': engagement_score,
                                'text_length': len(clean_text),
                                'fetched_at': datetime.now().isoformat(),
                                'source': 'custom_feed',
                                'feed_uri': feed_uri
                            }
                            posts.append(post_data)
            
            print(f"Fetched {len(posts)} posts from custom feed")
            return posts
            
        except Exception as e:
            print(f"Error fetching custom feed: {e}")
            return []

    # Popular feed URIs for easy access
    POPULAR_FEEDS = {
        'hot_classic': "at://did:plc:z72i7hdynmk6r22z27h6tvur/app.bsky.feed.generator/hot-classic",
        'discover': "at://did:plc:z72i7hdynmk6r22z27h6tvur/app.bsky.feed.generator/bsky-team-discover",
        # Add more popular feed URIs as discovered
    }