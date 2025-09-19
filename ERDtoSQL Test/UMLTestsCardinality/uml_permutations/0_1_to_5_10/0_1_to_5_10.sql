CREATE TABLE Player (
    PID VARCHAR(255),
    PName VARCHAR(255),
    PRIMARY KEY (PID)
);

-- Added FK to Player because StorageArea is the many side.

CREATE TABLE StorageArea (
    RID VARCHAR(255) NOT NULL,
    RID VARCHAR(255),
    size VARCHAR(255),
    Location VARCHAR(255),
    PRIMARY KEY (RID),
    FOREIGN KEY (PID) REFERENCES Player(PID)
);