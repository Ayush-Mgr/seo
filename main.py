import os
from typing import Dict
import serpapi

SOCIAL_MEDIA_DOMAINS = [
    "reddit.com", "quora.com", "instagram.com", "facebook.com", 
    "twitter.com", "x.com", "linkedin.com", "pinterest.com", 
    "tiktok.com", "youtube.com"
]

def track_rankings(location: str, search_dict: Dict[str, str], api_key: str):
    """
    Executes rank tracker lifecycle across a dictionary of keywords and target URLs
    using SerpAPI.
    """
    results_dict = {}
    client = serpapi.Client(api_key=api_key)

    for keyword, target_url in search_dict.items():
        print(f"Tracking keyword: '{keyword}' for URL: '{target_url}'")
        try:
            results = client.search({
                "q": keyword,
                "location": location,
                "hl": "en",
                "gl": "us",
                "google_domain": "google.com",
                "num": 50  # depth ~50 results
            })
            
            rank = None
            organic_results = results.get("organic_results", [])
            
            # The organic_results list contains dictionaries with 'position' and 'link'.
            for result in organic_results:
                link = result.get("link", "")
                clean_link = link.rstrip('/')
                target_clean = target_url.rstrip('/')
                
                # Ignore social media links
                if any(domain in clean_link for domain in SOCIAL_MEDIA_DOMAINS):
                    continue
                
                if target_clean in clean_link:
                    rank = result.get("position")
                    print(f" -> Found match at rank {rank}!")
                    break
                    
            results_dict[keyword] = rank
            
        except Exception as e:
            print(f"Failed to process keyword '{keyword}': {e}")
            results_dict[keyword] = None

    return results_dict

if __name__ == "__main__":
    my_location = "Austin, Texas, United States"
    
    my_search_dict = {
        "wiki": "https://www.wikipedia.org",
    }
    
    # Ideally should use an env variable for API key
    api_key = os.environ.get("SERPAPI_KEY", "secret_api_key") 
    
    print("Starting SEO Rank Tracker...")
    results = track_rankings(my_location, my_search_dict, api_key)
    
    print("\n--- Final Results ---")
    for keyword, rank in results.items():
        if rank:
            print(f"'{keyword}': Rank {rank}")
        else:
            print(f"'{keyword}': Not found in top 50")
