CREATE TABLE Player (
    PID VARCHAR(255),
    PName VARCHAR(255),
    PRIMARY KEY (PID)
);

-- Optional 1–1: FK in entity2

CREATE TABLE StorageArea (
    PID VARCHAR(255) UNIQUE,
    RID VARCHAR(255),
    size VARCHAR(255),
    Location VARCHAR(255),
    PRIMARY KEY (RID),
    FOREIGN KEY (PID) REFERENCES Player(PID)
);