import pytest
import os
from src.core.ledger import LedgerManager

@pytest.fixture
def temp_paths(tmp_path):
    ledger_path = tmp_path / "ledger.md"
    db_path = tmp_path / "faiss_index"
    return str(ledger_path), str(db_path)

def test_ledger_manager_missing_file_raises_error(temp_paths):
    ledger_path, db_path = temp_paths
    manager = LedgerManager(ledger_path=ledger_path, db_path=db_path)
    
    # Intentionally do NOT create the ledger.md file
    with pytest.raises(FileNotFoundError):
        manager.build_index()

def test_search_before_build_raises_error(temp_paths):
    ledger_path, db_path = temp_paths
    
    # Create an empty ledger file so it doesn't fail on missing file
    with open(ledger_path, "w") as f:
        f.write("Some facts here.")
        
    manager = LedgerManager(ledger_path=ledger_path, db_path=db_path)
    
    with pytest.raises(RuntimeError):
        manager.search_facts("test query")

def test_ledger_build_and_search_success(temp_paths):
    ledger_path, db_path = temp_paths
    
    with open(ledger_path, "w") as f:
        f.write("Fact 1: Zen writes code in Python.\n\nFact 2: Zen's project is TitanSwarm, written in Python.\n\nFact 3: Oranges are fruit.")
        
    manager = LedgerManager(ledger_path=ledger_path, db_path=db_path)
    manager.build_index()
    
    # We ask for the top 2 facts based on a Python query
    results = manager.search_facts("What programming language does Zen use?", top_k=2)
    
    assert len(results) == 2
    # The system should prioritize Fact 1 and 2, completely ignoring the irrelevant fruit fact
    assert "Oranges" not in results[0]
    assert "Python" in results[0]

