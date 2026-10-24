-- Migracion compatible con el esquema actual:
-- casa.nfc se conserva y no se modifica.
USE notvence;

CREATE TABLE IF NOT EXISTS casa_nfc (
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_casa INT NOT NULL,
    uid_tag VARCHAR(64) NOT NULL UNIQUE,
    token_hash CHAR(64) NOT NULL,
    nombre VARCHAR(80) NOT NULL DEFAULT 'Tag principal',
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ultimo_uso DATETIME NULL,
    CONSTRAINT fk_casa_nfc_casa
        FOREIGN KEY (id_casa) REFERENCES casa(id_casa)
        ON DELETE CASCADE
);

-- InnoDB crea automáticamente el índice necesario para la clave foránea.
