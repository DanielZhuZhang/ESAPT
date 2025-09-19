-- Added FK to StorageArea because Player is the many side.

CREATE TABLE Player (
    RID VARCHAR(255),
    PID VARCHAR(255),
    PName VARCHAR(255),
    PRIMARY KEY (PID),
    FOREIGN KEY (RID) REFERENCES StorageArea(RID)
);

CREATE TABLE StorageArea (
    RID VARCHAR(255),
    size VARCHAR(255),
    Location VARCHAR(255),
    PRIMARY KEY (RID)
);