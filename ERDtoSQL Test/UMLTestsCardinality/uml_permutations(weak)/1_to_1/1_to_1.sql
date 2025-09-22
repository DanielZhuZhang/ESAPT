CREATE TABLE Player (
    PID VARCHAR(255),
    PName VARCHAR(255),
    PRIMARY KEY (PID)
);

-- Weak 1–1: dependent PK = owner PK

CREATE TABLE StorageArea (
    PID VARCHAR(255),
    RID VARCHAR(255),
    size VARCHAR(255),
    Location VARCHAR(255),
    PRIMARY KEY (RID, PID),
    FOREIGN KEY (PID) REFERENCES Player(PID)
);