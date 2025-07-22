import os
import re
from datetime import datetime
from typing import List, Dict, Any
from dotenv import load_dotenv
from atproto import Client as AtProtoClient

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
        """Simple English detection"""
        # Remove emojis first for better detection
        clean_text = self.remove_emojis(text)
        
        # Check for common English words and patterns
        english_indicators = ['the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'its', 'may', 'new', 'now', 'old', 'see', 'two', 'who', 'boy', 'did', 'has', 'let', 'put', 'say', 'she', 'too', 'use']
        text_lower = clean_text.lower()
        english_word_count = sum(1 for word in english_indicators if word in text_lower)
        
        # Also check for non-Latin scripts (exclude posts with them)
        non_latin_pattern = re.compile(r'[\u0080-\uffff]')
        non_latin_chars = len(non_latin_pattern.findall(clean_text))
        
        # Consider it English if it has English words and low non-Latin character ratio
        return english_word_count >= 2 and (non_latin_chars / len(clean_text)) < 0.3 if clean_text else False


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
                    
                    # Filter: English, minimum length, not just URLs/mentions
                    if (len(text) >= min_length and 
                        self.is_english(text) and
                        not re.match(r'^[@#\s]*$', text)):  # Not just mentions/hashtags
                        
                        engagement_score = (
                            (post.post.like_count or 0) + 
                            (post.post.repost_count or 0) + 
                            (post.post.reply_count or 0)
                        )
                        
                        clean_text = self.remove_emojis(text).strip()
                        
                        post_data = {
                            'uri': post.post.uri,
                            'text': clean_text,
                            'original_text': text,
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
                    
                    if (len(text) >= min_length and 
                        self.is_english(text) and
                        not re.match(r'^[@#\s]*$', text)):
                        
                        engagement_score = (
                            (post.post.like_count or 0) + 
                            (post.post.repost_count or 0) + 
                            (post.post.reply_count or 0)
                        )
                        
                        clean_text = self.remove_emojis(text).strip()
                        
                        post_data = {
                            'uri': post.post.uri,
                            'text': clean_text,
                            'original_text': text,
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