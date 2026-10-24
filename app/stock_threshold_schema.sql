-- One-time migration: give existing products the previous low-stock default.
ALTER TABLE producto
    ADD COLUMN stock_minimo INT NOT NULL DEFAULT 3;
