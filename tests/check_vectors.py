from neo4j import GraphDatabase

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "Avyukt@TATA_RATAN2026"))
with driver.session() as session:
    result = session.run("MATCH (n:__Node__) WHERE n.embedding IS NOT NULL RETURN count(n) AS c")
    for r in result:
        print(f"Nodes with embeddings: {r['c']}")
    
    result = session.run("MATCH (n:__Node__) RETURN count(n) AS c")
    for r in result:
        print(f"Total __Node__s: {r['c']}")
