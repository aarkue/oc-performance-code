import os
import pandas as pd
import csv,os
import shutil

from neo4j import GraphDatabase
from neo4j import Driver

class OcedCsvImportQueryLibrary:

    @staticmethod
    # create index on nodes with label 'node_label', for a specific attribute 'id'
    def q_create_index(nodel_label, id):
        # create index if it does not exist yet, to speed up loading and querying
        index_query = f'CREATE INDEX {nodel_label}_{id} IF NOT EXISTS FOR (n:{nodel_label}) ON (n.{id})'
        print(index_query)
        return index_query

    @staticmethod
    # delete all relationships
    def q_delete_relations():
        q = f'MATCH ()-[r]->() CALL (r) {{ DELETE r }} IN TRANSACTIONS OF 1000 ROWS;'
        print(q)
        return q

    @staticmethod
    # delete all nodes
    def q_delete_nodes():
        q = f'MATCH (n) CALL (n) {{ DELETE n }} IN TRANSACTIONS OF 1000 ROWS;'
        print(q)
        return q


    @staticmethod
    # Use Neo4j's bulk import from CSV to create on :event node per record in CSV file
    # - 'fileName' is the system file path to the CSV file from which Neo4j will load
    # - 'logHeader' the list of attribute names of the CSV file
    # - an optional `LogID` to distinguish events coming from different event logs
    def q_load_csv_as_nodes(fileName, csvHeader, nodeLabel):

        # import each row of the CSV one by one, as variable 'line' 
        query_str = f'LOAD CSV WITH HEADERS FROM \"file:///{fileName}\" as line\n'
        query_str += 'CALL (line) {\n'
        query_str += ' WITH line\n'

        # per line create a node
        query_str = query_str + f' CREATE (e:{nodeLabel} {{ '
        # subsequent lines specify how the attribute of event e are set (from "line')

        # for each colum in the header, set attribute 'column' of event e to the value line.column
        for col in csvHeader:
            # allow type conversion by Neo4j during import
            if col in ['time','timestamp','start','end']:
                # tell Neo4j to typecast timestamp attributes to dateTime during import
                colValue = f'datetime(line.{col})'
            else:
                # every other attribute is just the value stored in the column in that line
                colValue = 'line.'+col

            # distinguish final event to close the CREATE query properly
            if (csvHeader.index(col) < len(csvHeader)-1):
                query_str = query_str + f' {col}: {colValue},'
            else:
                query_str = query_str + f' {col}: {colValue} }})'

        query_str += '\n'    
        query_str += '} IN TRANSACTIONS OF 1000 ROWS;'

        print(query_str)

        return query_str
    
    @staticmethod
    def q_link_node_to_node(sourceNode, sourceAttribute, relationship, targetNode, targetAttribute):
        query_str = f'''
            MATCH (t:{targetNode}) WITH t
            MATCH (s:{sourceNode} {{ {sourceAttribute}: t.{targetAttribute} }}) WITH s,t
            MERGE (s)-[:{relationship}]->(t)'''
        print(query_str)
        return query_str
    
    @staticmethod
    def q_load_csv_as_relation(fileName, csvSourceId, sourceLabel, sourceIdAttr, csvRelationType, relationship, csvTargetId, targetLabel, targetIdAttribute):
        # import each row of the CSV one by one, as variable 'line' 
        query_str = f'''
            LOAD CSV WITH HEADERS FROM \"file:///{fileName}\" as line
            CALL (line) {{
             WITH line
              MATCH (s:{sourceLabel} {{ {sourceIdAttr}:line.{csvSourceId} }} )
              MATCH (n:{targetLabel} {{ {targetIdAttribute}:line.{csvTargetId} }} )
              MERGE (s) -[r:{relationship}]-> (n) ON CREATE SET r.type=line.{csvRelationType}
            }} IN TRANSACTIONS OF 1000 ROWS;'''

        print(query_str)

        return query_str
    
    # @staticmethod
    # def q_add_df_relation():
    #     query_str = f'''
    #         MATCH (n:Entity)
    #         MATCH (n)<-[:CORR]-(e)
    #         WITH n, e AS nodes ORDER BY e.time, ID(e)
    #         WITH n, collect(nodes) AS event_node_list
    #         UNWIND range(0, size(event_node_list)-2) AS i
    #         WITH n, event_node_list[i] AS e1, event_node_list[i+1] AS e2
    #         MERGE (e1)-[df:DF {{EntityType:n.EntityType, ID:n.ID}}]->(e2)'''
    #     print(query_str)
    #     return query_str

    @staticmethod
    def q_load_csv_as_e2o_relation(fileName):
        return OcedCsvImportQueryLibrary.q_load_csv_as_relation(fileName, "eventId", "Event", "id", "qualifier", "CORR", "objectId", "Entity", "id")

class OcedCsvImport:
    def __init__(self, driver: Driver):
        self.driver = driver

    # execute a query
    def _run_query(self, query: str):
        with self.driver.session() as session:
            result = session.run(query).single()
            if result != None: 
                return result.value()
            else:
                return None

    # load csv header (attribute names) from import file
    @staticmethod
    def _get_csv_header(fileName):
        with open(fileName) as f:
            reader = csv.reader(f)
            logHeader = list(next(reader))
            f.close()
        return logHeader

    # create index on nodes with label 'node_label', for a specific attribute 'id'
    def _create_index(self, nodel_label, id):
        index_query = OcedCsvImportQueryLibrary.q_create_index(nodel_label, id)
        self._run_query(index_query)

    # import records from 'csv' file as nodes with label 'node_label'
    def _import_nodes(self, csv_path, csv_file, node_label):
        print("Import "+node_label+" from "+csv_file)
        
        # need full path to csv file for correct import query for neo4j
        full_path = os.path.realpath(csv_path+csv_file)
        # need csv header to generate load query
        header = OcedCsvImport._get_csv_header(full_path)
        # generate query for loading nodes
        load_query = OcedCsvImportQueryLibrary.q_load_csv_as_nodes(csv_file, header, node_label)
        # run the query
        self._run_query(load_query)

    # import ocel2 events from prepared event table csv
    def import_events(self):
        self._create_index("Event", "id")
        self._import_nodes(self.csv_events, "Event")

    # import ocel2 objects from prepared object table csv
    def import_objects(self):
        self._create_index("Entity", "id")
        self._import_nodes(self.csv_objects, "Entity")

    # import ocel2 object attributes from prepared attribute table csv
    def import_object_attributes(self):
        # import attribute nodes        
        self._import_nodes(self.csv_object_attributes, "EntityAttribute")
        # link attribute nodes to object nodes
        link_query = OcedCsvImportQueryLibrary.q_link_node_to_node("Entity", "id", "HAS_ATTRIBUTE", "EntityAttribute", "id")
        self._run_query(link_query)

    # import ocel2 event-object relation from relation tabel csv
    def import_e2o_relation(self):

        print("Import relation from "+self.csv_relations_e2o)

        # need full path to csv file for correct import query for neo4j
        full_path = os.path.realpath(self.csv_relations_e2o)
        # load the event-object relation csv as relation
        ### resolve 'eventId' to an 'Event' node with matching 'id'
        ### create CORR relation with type 'qualifier'
        ### resolve 'objectId' to an 'Entity' node with matching 'id' 
        load_query = OcedCsvImportQueryLibrary.q_load_csv_as_relation(full_path, "eventId", "Event", "id", "qualifier", "CORR", "objectId", "Entity", "id")
        self._run_query(load_query)

class Neo4jModelStrong:
    name = "neo4jstrong"

    def __init__(self) -> None:
        # connection to Neo4J database
        self._driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "12345678"))
        self._db_instance_dir = "C:/Users/dfahland/.Neo4jDesktop2/Data/dbmss/dbms-3ed2a1de-63f0-4617-858f-910db803a1f9"
        self._db_instance_import_dir = self._db_instance_dir+"/import/"

        # ensure import directory exists
        if not os.path.exists(self._db_instance_import_dir):  
            os.makedirs(self._db_instance_import_dir)

        self._import = OcedCsvImport(self._driver)
    
    #def setup(self, dataset: Dataset) -> None:
    def setup(self) -> None:

        self._import._run_query(OcedCsvImportQueryLibrary.q_delete_relations())
        self._import._run_query(OcedCsvImportQueryLibrary.q_delete_nodes())

        import_path = "./data/bpic17/bpic17-strong-csv/"
        
        import_path_nodes = os.path.realpath(import_path + "nodes/")
        for file in os.listdir(import_path_nodes):
            if file.endswith(".csv"):
                f = os.path.join(import_path_nodes, file)

                # copy file to neo4j import directory for loading
                dest = os.path.join(self._db_instance_import_dir, file)
                shutil.copy(f, dest)

                label = file[:-4]
                self._import._create_index(label, "id")
                self._import._import_nodes(self._db_instance_import_dir, file, label)


        import_path_relations = os.path.realpath(import_path + "rels/")
        for file in os.listdir(import_path_relations):
            if file.endswith(".csv"):
                f = os.path.join(import_path_relations, file)

                # copy file to neo4j import directory for loading
                dest = os.path.join(self._db_instance_import_dir, file)
                shutil.copy(f, dest)

                # split 'file' on '__' character
                label_to_split = file[:-4]
                labels = label_to_split.split('__')
                
                print(labels)
                if labels[0] == "E2O":
                    rel_label = "CORR"
                if labels[0] == "O2O":
                    rel_label = "REL"
                if labels[0] == "Attrs":
                    rel_label = "HAS_ATTRIBUTE"

                source_label = labels[1]
                target_label = labels[2]

                load_query = OcedCsvImportQueryLibrary.q_load_csv_as_relation(
                    fileName=file,
                    csvSourceId="start_id",
                    sourceLabel=source_label,
                    sourceIdAttr="id",
                    csvRelationType="qualifier",
                    relationship=rel_label,
                    csvTargetId="end_id",
                    targetLabel=target_label,
                    targetIdAttribute="id")
                self._import._run_query(load_query)
                        

run_neo4j = Neo4jModelStrong()
run_neo4j.setup()
