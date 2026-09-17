import json
import random
import os
import copy

NAMES = ["Alice", "Bob", "Charlie", "Diana", "Evan", "Fiona", "George", "Hannah"]
DOMAINS = ["corp.com", "startup.io", "enterprise.net", "health.org", "tech.ai"]
AMOUNTS = ["$100", "$250", "$500", "$1200", "$450"]
IDS = ["INV-1111", "INV-2222", "INV-3333", "INV-4444"]

def load_jsonl(path):
    data = []
    if os.path.exists(path):
        with open(path, 'r') as f:
            for line in f:
                if line.strip():
                    data.append(json.loads(line))
    return data

def expand(records, prefix=""):
    expanded = []
    for r in records:
        for i in range(8):
            nr = copy.deepcopy(r)
            nr["id"] = f"{prefix}{r['id']}_var{i}"
            
            # Simple replacements for variety
            n = random.choice(NAMES)
            d = random.choice(DOMAINS)
            a = random.choice(AMOUNTS)
            id_ = random.choice(IDS)
            
            # This is a very simplistic string replacement for volume testing.
            # In production, we'd use an LLM for semantic variation.
            nr["sender"] = f"{n.lower()}@{d}"
            
            for field in ["subject", "body", "ground_truth_reply"]:
                if field in nr:
                    nr[field] = nr[field].replace("INV-8821", id_).replace("INV-9940", id_)
                    nr[field] = nr[field].replace("Marcus", n).replace("Elena", n).replace("Tom", n)
            
            expanded.append(nr)
    return expanded

if __name__ == "__main__":
    hist = load_jsonl("data/historical_support_emails.jsonl")
    tests = load_jsonl("data/test_emails.jsonl")
    
    if len(hist) < 50:
        print(f"Expanding dataset from {len(hist)} to ~104...")
        hist_exp = expand(hist, "h_")
        test_exp = expand(tests, "t_")
        
        with open("data/historical_support_emails.jsonl", "w") as f:
            for r in hist_exp:
                f.write(json.dumps(r) + "\n")
                
        with open("data/test_emails.jsonl", "w") as f:
            for r in test_exp:
                f.write(json.dumps(r) + "\n")
                
        print(f"Saved {len(hist_exp)} historical and {len(test_exp)} test cases.")
    else:
        print("Dataset already expanded.")
