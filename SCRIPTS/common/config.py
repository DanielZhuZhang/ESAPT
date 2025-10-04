instruction = """You are given an image of a conceptual ER diagram that could either be (Chen or Crow's Foot).
        Your job is to (1) extract the ER model strictly from visual cues, and (2) produce cumulative SQL code step-by-step.

        Definitions

        Chen Notation
        - Entities are rectangles.
        - Relationships are diamonds, connected to the entities they relate.
        - Cardinality: 1 means one; M and N means many; 1 to M means one-to-many; M to N or N to M is many-to-many.
        - Keys: Primary keys are text underlined with a solid line. Partial keys are underlined with a dashed line.
        - Pay close attention to whether the text is underlined; spacing between the text and the underline can be small.

        Crow’s Foot Notation
        - Entities are rectangles.
        - Relationships are lines with symbols at the ends: crow’s foot (<) = many; single line (|) = one.
        - One-to-many is represented by a single line on one end and a crow’s foot on the other.

        General Rules
        - Many-to-many relationships require creating a separate table to represent the association.
        - Do not assume attributes or keys based on names alone—only use explicit diagram features.
        - Only create foreign keys when there is a direct relationship between entities.
        - If more than one attribute is underlined. Instead of adding the words PRIMARY KEY at the end of one of them, put under the attributes the code PRIMARY KEY(attribute1, attribute2, ...) for each attribute that is underlined in the entity.
        - If only one attribute is underlined for an entity, add the words PRIMARY KEY next to that attribute,
        - If a table has a foreign key, the table that the foreign key points to must be created before the table with the foreign key.

        SQL CONVENTIONS
        - Dialect: PostgreSQL 15+
        - Constraints: use inline constraints.
        - Use NOT NULL when total participation requires it.
        - For weak entities: composite PK includes owner PK + weak key; add FK to owner with ON DELETE CASCADE.
        - For 1:1 relationships: place the FK on the total-participation side and add UNIQUE to enforce 1:1.

        STEP-BY-STEP MAPPING
        Step 1 — Strong Entities
        - Create one table per strong entity with all simple attributes.
        - Use underlined attributes as the primary key. Do not invent surrogate keys unless the diagram lacks a key.

        Step 2 — Weak Entities
        - Create one table per weak entity with its simple attributes.
        - Always add FK to the owner; composite PK = owner PK + partial/own key (if present). Use ON DELETE CASCADE on that FK.

        Step 3 — Binary 1:1 Relationships Non-Identifying Relations
        - Include the PK of one entity as an FK in the other(not as a composite primary), choosing the side with total participation if shown.
        - Add relationship attributes into that same table.
        - Enforce 1:1 with UNIQUE on the FK and NOT NULL if participation is total.

        Step 4 — Binary 1:M Relationships Non-Identifying Relations
        - Put the 1-side PK as an FK(not as a composite primary key) as  in the M-side table.
        - Include any relationship attributes in the M-side table.
        - Use NOT NULL if the M-side participation is total.
        - If the foreign key points to a table that has a create statement after the table the foreign key is being added to in this step, move the table's create statement below the one that it points to.

        Step 5 — Binary M:N Relationships
        - Create a new join table.
        - Primary key = combination of the participating entities’ PKs (and include relationship attributes).

        OUTPUT FORMAT
        Print sections in the order below, each bounded by single-line markers:

        === RECOGNIZED FROM IMAGE ===
        (Plain text list of entities, attributes, keys (underline/dashed), relationships, and cardinalities derived from the image only.)

        === STEP 1 — STRONG ENTITIES (SQL) ===
        -- SQL for Step 1 only
        === EXPLANATION / ASSUMPTIONS / ANOMALIES FOR STEP 1===
        - Assumptions & Ambiguities: bullet list
        - Explanation

        === STEP 2 — WEAK ENTITIES (SQL) ===
        -- SQL After Applying Step 2

        === EXPLANATION / ASSUMPTIONS / ANOMALIES FOR STEP 2===
        - Assumptions & Ambiguities: bullet list
        - Explanation

        === STEP 3 — BINARY 1:1 (SQL) ===
        -- SQL After Applying Step 3

        === EXPLANATION / ASSUMPTIONS / ANOMALIES FOR STEP 3===
        - Assumptions & Ambiguities: bullet list
        - Explanation

        === STEP 4 — BINARY 1:N (SQL) ===
        -- SQL After Applying Step 4

        === EXPLANATION / ASSUMPTIONS / ANOMALIES FOR STEP 4===
        - Assumptions & Ambiguities: bullet list
        - Explanation

        === STEP 5 — BINARY M:N (SQL) ===
        -- SQL After Applying Step 5

        === EXPLANATION / ASSUMPTIONS / ANOMALIES FOR STEP 5===
        - Assumptions & Ambiguities: bullet list
        - Explanation

        STRICT RULES
        - Use the exact section headers above (including capitalization and punctuation).
        - Include ALL sections even if some are empty; 
        - Each column only contains its datatype and NOT NULL (if applicable).  
        - All constraints (PRIMARY KEY, FOREIGN KEY, UNIQUE) go at the bottom of the table definition, All constraints must be declared separately, each on its own line at the end of the column list.
        - Do not output anything outside these sections.
        - For SQL print the cumulative output with each prior step
        - In the explanation avoid long lines, create a new line and continue if one line exceeds 60 characters"""
