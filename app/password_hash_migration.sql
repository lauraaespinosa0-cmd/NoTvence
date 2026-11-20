-- Widen the existing password column to fit Argon2id hashes.
-- Preserve the column's current NULL/NOT NULL constraint if it differs.
ALTER TABLE usuario
MODIFY COLUMN contrasena VARCHAR(255) NOT NULL;
