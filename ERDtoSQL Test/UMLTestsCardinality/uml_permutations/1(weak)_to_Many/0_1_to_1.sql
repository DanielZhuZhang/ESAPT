-- Optional 1–1: FK in entity1

CREATE TABLE Player (
    RID VARCHAR(255) UNIQUE,
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