#!/usr/bin/env python3
import hashlib
import networkx as nx
import random
from typing import Dict, List, Set, Tuple, Optional

# --- CORE MATCHING ENGINE (MODIFIED FOR TRAY/UI) ---

def build_compatibility_graph(users: List[Dict], history: Dict[str, List[str]]) -> nx.Graph:
    """
    Builds graph from passed-in data rather than local files.
    'history' is now expected as user_id -> list of matched_ids.
    """
    G = nx.Graph()
    for user in users:
        G.add_node(user['id'], name=user['name'], email=user['email'])
    
    user_ids = [user['id'] for user in users]
    for i, user1 in enumerate(user_ids):
        for user2 in user_ids[i+1:]:
            # Convert list history to set for speed
            user1_history = set(history.get(user1, []))
            if user2 not in user1_history:
                G.add_edge(user1, user2)
    return G

def find_maximum_matching(G: nx.Graph) -> Set[Tuple[str, str]]:
    matching_set = nx.max_weight_matching(G, maxcardinality=True)
    final_matching = {tuple(sorted([n1, n2])) for n1, n2 in matching_set}
    return final_matching

def create_triad(matches: Set[Tuple[str, str]], 
                all_users: List[Dict], 
                history: Dict[str, List[str]]) -> Optional[Tuple[str, str, str]]:
    matched_ids = {u for pair in matches for u in pair}
    all_ids = {u['id'] for u in all_users}
    unmatched = list(all_ids - matched_ids)
    
    if not unmatched: return None
    
    unmatched_id = unmatched[0]
    unmatched_history = set(history.get(unmatched_id, []))
    
    # Try to find a pair where the 3rd person hasn't met either
    for pair in matches:
        if pair[0] not in unmatched_history and pair[1] not in unmatched_history:
            return (pair[0], pair[1], unmatched_id)
    
    # Fallback to a random pair if perfect compatibility isn't possible
    random_pair = list(matches)[0]
    return (random_pair[0], random_pair[1], unmatched_id)

# --- NEW: INTEGRATION WRAPPERS ---

def generate_new_history(current_history: Dict, matches: Set, triad: Optional[Tuple]) -> Dict:
    """Returns a new history object to be saved back to Google Sheets/Tray"""
    new_history = {k: list(v) for k, v in current_history.items()} # Copy
    
    def add_match(u1, u2):
        if u1 not in new_history: new_history[u1] = []
        if u2 not in new_history: new_history[u2] = []
        if u2 not in new_history[u1]: new_history[u1].append(u2)
        if u1 not in new_history[u2]: new_history[u2].append(u1)

    for u1, u2 in matches:
        add_match(u1, u2)
    if triad:
        add_match(triad[0], triad[1])
        add_match(triad[1], triad[2])
        add_match(triad[0], triad[2])
        
    return new_history

def format_matches_for_tray(matches: Set, triad: Optional[Tuple], users: List[Dict]) -> List[Dict]:
    """Formats matches into a clean list for Tray to send to Braze"""
    lookup = {u['id']: u for u in users}
    output = []
    
    for u1, u2 in matches:
        output.append({
            "type": "pair",
            "person_a": lookup[u1],
            "person_b": lookup[u2]
        })
    
    if triad:
        output.append({
            "type": "triad",
            "person_a": lookup[triad[0]],
            "person_b": lookup[triad[1]],
            "person_c": lookup[triad[2]]
        })
    return output

# --- MAIN EXECUTION FUNCTION FOR UI/API ---

def run_workflow_logic(user_list: List[Dict], history_data: Dict):
    """
    This is the function your UI or API will call.
    It takes Python objects and returns Python objects.
    """
    G = build_compatibility_graph(user_list, history_data)
    matches = find_maximum_matching(G)
    
    triad = None
    if len(user_list) % 2 != 0:
        triad = create_triad(matches, user_list, history_data)
        if triad:
            matches.remove(tuple(sorted([triad[0], triad[1]])))
            
    return {
        "tray_payload": format_matches_for_tray(matches, triad, user_list),
        "updated_history": generate_new_history(history_data, matches, triad)
    }