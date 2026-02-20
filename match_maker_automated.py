#!/usr/bin/env python3
import networkx as nx
import random
from typing import Dict, List, Set, Tuple, Optional

# ==========================================
# 1. CORE MATCHING ENGINE (The "Brain")
# ==========================================

def build_compatibility_graph(users: List[Dict], history: Dict[str, List[str]]) -> nx.Graph:
    """
    Nodes = People (by Email)
    Edges = Possible matches (only if they haven't matched before)
    """
    G = nx.Graph()
    
    # Add nodes with metadata
    for user in users:
        # We use Email as the unique ID for simplicity in Sheets
        email = user['email']
        G.add_node(email, name=user['name'])
    
    user_emails = [user['email'] for user in users]
    
    # Add edges between people who have NOT matched before
    for i, email1 in enumerate(user_emails):
        for email2 in user_emails[i+1:]:
            past_matches = history.get(email1, [])
            if email2 not in past_matches:
                G.add_edge(email1, email2)
    
    return G

def find_maximum_matching(G: nx.Graph) -> Set[Tuple[str, str]]:
    """Finds the optimal pairs using NetworkX"""
    matching_set = nx.max_weight_matching(G, maxcardinality=True)
    return {tuple(sorted([n1, n2])) for n1, n2 in matching_set}

def create_triad(matches: Set[Tuple[str, str]], 
                all_users: List[Dict], 
                history: Dict[str, List[str]]) -> Optional[Tuple[str, str, str]]:
    """Handles the 'odd person out' by creating a group of 3"""
    matched_emails = {email for pair in matches for email in pair}
    all_emails = {u['email'] for u in all_users}
    unmatched = list(all_emails - matched_emails)
    
    if not unmatched:
        return None
    
    unmatched_email = unmatched[0]
    unmatched_history = set(history.get(unmatched_email, []))
    
    # Prioritize a pair where the unmatched person hasn't met either member
    for pair in matches:
        if pair[0] not in unmatched_history and pair[1] not in unmatched_history:
            return (pair[0], pair[1], unmatched_email)
    
    # Fallback: Just pick the first available pair
    if matches:
        lucky_pair = list(matches)[0]
        return (lucky_pair[0], lucky_pair[1], unmatched_email)
    return None

# ==========================================
# 2. INTEGRATION WRAPPERS (The "Translator")
# ==========================================

def transform_sheet_history_to_dict(history_rows: List[Dict]) -> Dict[str, List[str]]:
    """
    Turns the 'MatchHistory' tab rows into a lookup dictionary.
    Expects keys: 'Person A (Email)', 'Person B (Email)'
    """
    history_dict = {}
    for row in history_rows:
        p1 = row.get('Person A (Email)')
        p2 = row.get('Person B (Email)')
        
        if p1 and p2:
            history_dict.setdefault(p1, []).append(p2)
            history_dict.setdefault(p2, []).append(p1)
    return history_dict

def format_matches_for_tray(matches: Set[Tuple[str, str]], triad: Optional[Tuple], users: List[Dict]) -> List[Dict]:
    """Prepares a clean list for Tray to loop through for Braze emails"""
    lookup = {u['email']: u for u in users}
    payload = []
    
    for email1, email2 in matches:
        payload.append({
            "match_type": "pair",
            "person_a": lookup[email1],
            "person_b": lookup[email2]
        })
        
    if triad:
        payload.append({
            "match_type": "triad",
            "person_a": lookup[triad[0]],
            "person_b": lookup[triad[1]],
            "person_c": lookup[triad[2]]
        })
    return payload

# ==========================================
# 3. MAIN WORKFLOW EXECUTION
# ==========================================

def run_matching_workflow(active_participants: List[Dict], raw_history: List[Dict]):
    """
    The main entry point for your UI or Tray Trigger.
    
    Args:
        active_participants: List of users from 'Participants' tab (filtered for PTO)
        raw_history: List of rows from the 'MatchHistory' tab
    """
    # 1. Prepare history
    formatted_history = transform_sheet_history_to_dict(raw_history)
    
    # 2. Build Graph and find pairs
    G = build_compatibility_graph(active_participants, formatted_history)
    matches = find_maximum_matching(G)
    
    # 3. Handle odd numbers
    triad = None
    if len(active_participants) % 2 != 0:
        triad = create_triad(matches, active_participants, formatted_history)
        if triad:
            # Remove the pair that was converted into a triad
            matches.remove(tuple(sorted([triad[0], triad[1]])))
    
    # 4. Return formatted results
    return format_matches_for_tray(matches, triad, active_participants)

# Example usage (for testing):
# if __name__ == "__main__":
#     users = [{"email": "a@test.com", "name": "Alice"}, {"email": "b@test.com", "name": "Bob"}]
#     history = [{"Person A (Email)": "a@test.com", "Person B (Email)": "b@test.com"}]
#     print(run_matching_workflow(users, history))
