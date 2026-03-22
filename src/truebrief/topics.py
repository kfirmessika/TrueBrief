import json
import os
from typing import List, Dict

class TopicManager:
    """
    Manages the persistence of surveillance topics.
    Files are saved to data/topics.json
    """
    def __init__(self, data_dir="data"):
        self.file_path = os.path.join(data_dir, "topics.json")
        self._ensure_file()
        
    def _ensure_file(self):
        # Ensure directory exists first
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        
        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w') as f:
                json.dump([], f)

                
    def get_all_topics(self) -> List[Dict]:
        """Returns list of topics: [{'name': 'Nvidia', 'sources': {...}}]"""
        try:
            with open(self.file_path, 'r') as f:
                return json.load(f)
        except:
            return []
            
    def add_topic(self, topic_name: str, sources: Dict) -> Dict:
        """
        Adds a new topic to the list.
        Sources should be output from Librarian: {'rss': [], 'static': []}
        """
        topics = self.get_all_topics()
        
        # Check defaults
        new_entry = {
            "name": topic_name,
            "sources": sources,
            "active": True,
            "last_scan": None
        }
        
        # Remove if identifier exists (simple update)
        topics = [t for t in topics if t['name'].lower() != topic_name.lower()]
        topics.append(new_entry)
        
        with open(self.file_path, 'w') as f:
            json.dump(topics, f, indent=2)
            
        return new_entry

    def delete_topic(self, topic_name: str):
        topics = self.get_all_topics()
        topics = [t for t in topics if t['name'].lower() != topic_name.lower()]
        with open(self.file_path, 'w') as f:
            json.dump(topics, f, indent=2)
