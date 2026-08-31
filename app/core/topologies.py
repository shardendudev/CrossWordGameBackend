from typing import List, Dict, Any

# 6-Movie Interlocking Clustered Topologies
TOPOLOGIES_6_MOVIES: List[Dict[str, Any]] = [
    {
        "id": "grid_6_movies_cluster_a",
        "grid_size": 10,
        "slots": [
            {"slot_id": "S1", "direction": "H", "start_row": 2, "start_col": 1, "length": 7},
            {"slot_id": "S2", "direction": "V", "start_row": 1, "start_col": 3, "length": 6},
            {"slot_id": "S3", "direction": "V", "start_row": 1, "start_col": 6, "length": 8},
            {"slot_id": "S4", "direction": "H", "start_row": 5, "start_col": 4, "length": 6},
            {"slot_id": "S5", "direction": "H", "start_row": 7, "start_col": 3, "length": 7},
            {"slot_id": "S6", "direction": "V", "start_row": 4, "start_col": 8, "length": 5},
        ]
    },
    {
        "id": "grid_6_movies_cluster_b",
        "grid_size": 10,
        "slots": [
            {"slot_id": "S1", "direction": "H", "start_row": 1, "start_col": 2, "length": 8},
            {"slot_id": "S2", "direction": "V", "start_row": 1, "start_col": 4, "length": 7},
            {"slot_id": "S3", "direction": "V", "start_row": 1, "start_col": 7, "length": 8},
            {"slot_id": "S4", "direction": "H", "start_row": 4, "start_col": 1, "length": 8},
            {"slot_id": "S5", "direction": "H", "start_row": 7, "start_col": 2, "length": 8},
            {"slot_id": "S6", "direction": "V", "start_row": 3, "start_col": 9, "length": 6},
        ]
    }
]

EASY_TOPOLOGIES: List[Dict[str, Any]] = TOPOLOGIES_6_MOVIES
MEDIUM_TOPOLOGIES: List[Dict[str, Any]] = TOPOLOGIES_6_MOVIES
HARD_TOPOLOGIES: List[Dict[str, Any]] = TOPOLOGIES_6_MOVIES

def transformTopology(topology: Dict[str, Any], rotation: int = 0, flip_h: bool = False, flip_v: bool = False) -> Dict[str, Any]:
    """Applies spatial rotation (0, 90, 180, 270 deg) and flips to a topology."""
    size = topology.get("grid_size", 10)
    transformed_slots = []
    
    for slot in topology["slots"]:
        r, c, length, direction = slot["start_row"], slot["start_col"], slot["length"], slot["direction"]
        
        if flip_h:
            if direction == "H":
                c = size - c - length
            else:
                c = size - c - 1
                
        if flip_v:
            if direction == "V":
                r = size - r - length
            else:
                r = size - r - 1
                
        transformed_slots.append({
            "slot_id": slot["slot_id"],
            "direction": direction,
            "start_row": r,
            "start_col": c,
            "length": length
        })
        
    return {
        "id": f"{topology['id']}_r{rotation}_fh{flip_h}_fv{flip_v}",
        "grid_size": size,
        "slots": transformed_slots
    }