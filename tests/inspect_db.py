from neo4j import GraphDatabase

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "Avyukt@TATA_RATAN2026"))
with driver.session() as session:
    result = session.run("CALL db.labels()")
    labels = [record[0] for record in result]
    print("Labels in DB:", labels)
    
    for label in labels:
        count = session.run(f"MATCH (n:{label}) RETURN count(n)").single()[0]
        print(f"Count for {label}: {count}")

driver.close()
