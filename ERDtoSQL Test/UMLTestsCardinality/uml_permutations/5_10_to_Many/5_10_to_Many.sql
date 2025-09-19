CREATE TABLE Player (
    PID VARCHAR(255),
    PName VARCHAR(255),
    PRIMARY KEY (PID)
);

CREATE TABLE StorageArea (
    RID VARCHAR(255),
    size VARCHAR(255),
    Location VARCHAR(255),
    PRIMARY KEY (RID)
);

-- Join table for many-to-many between Player and StorageArea.

CREATE TABLE owns (
    PID VARCHAR(255),
    RID VARCHAR(255),
    PRIMARY KEY (RID, PID),
    FOREIGN KEY (RID) REFERENCES StorageArea(RID),
    FOREIGN KEY (PID) REFERENCES Player(PID)
);