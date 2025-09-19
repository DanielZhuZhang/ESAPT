-- Weak 1–1: dependent PK = owner PK

CREATE TABLE Player (
    RID VARCHAR(255),
    PID VARCHAR(255),
    PName VARCHAR(255),
    PRIMARY KEY (RID, PID),
    FOREIGN KEY (RID) REFERENCES StorageArea(RID)
);

CREATE TABLE StorageArea (
    RID VARCHAR(255),
    size VARCHAR(255),
    Location VARCHAR(255),
    PRIMARY KEY (RID)
);