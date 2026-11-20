import unittest
from datetime import date, timedelta
from unittest.mock import patch

from pydantic import ValidationError

from app.auth import create_access_token, decode_access_token
from app.database import get_connection
from app.passwords import hash_password, verify_password_and_update
from app.schemas import ProductCreate
from app.store import dashboard_data, product_alerts


class ProductValidationTests(unittest.TestCase):
    def test_product_strips_required_text_and_accepts_expiry(self):
        product = ProductCreate(
            nombre="  Leche  ",
            categoria="Alimentos",
            presentacion="  Litro (L) ",
            cantidad=2,
            ubicacion="  Nevera ",
            vence="2030-05-14",
        )

        self.assertEqual(product.nombre, "Leche")
        self.assertEqual(product.presentacion, "Litro (L)")
        self.assertEqual(product.ubicacion, "Nevera")
        self.assertEqual(product.vence, "2030-05-14")

    def test_product_rejects_invalid_expiry_and_negative_quantity(self):
        base = {
            "nombre": "Leche",
            "categoria": "Alimentos",
            "presentacion": "Litro",
            "cantidad": 1,
            "ubicacion": "Nevera",
        }

        for invalid in (
            {**base, "vence": "2030-02-30"},
            {**base, "cantidad": -1},
            {**base, "nombre": "   "},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                ProductCreate(**invalid)


class InventoryLogicTests(unittest.TestCase):
    def test_stock_threshold_includes_equal_quantity(self):
        self.assertEqual(product_alerts(3, None, stock_limit=3), ["Stock bajo"])
        self.assertEqual(product_alerts(4, None, stock_limit=3), [])

    def test_expiry_alerts_cover_due_soon_and_expired_products(self):
        soon = (date.today() + timedelta(days=7)).isoformat()
        expired = (date.today() - timedelta(days=1)).isoformat()

        self.assertEqual(product_alerts(10, soon, stock_limit=3), ["Por vencer"])
        self.assertEqual(product_alerts(10, expired, stock_limit=3), ["Vencido"])
        self.assertEqual(
            product_alerts(1, soon, stock_limit=3),
            ["Stock bajo", "Por vencer"],
        )

    def test_dashboard_summarizes_inventory_and_expiring_products(self):
        soon = (date.today() + timedelta(days=2)).isoformat()
        products = [
            {"nombre": "Arroz", "categoria": "Alimentos", "cantidad": 2, "vence": soon, "stock_minimo": 3},
            {"nombre": "Jugo", "categoria": "Bebidas", "cantidad": 8, "vence": None, "stock_minimo": 3},
        ]

        summary = dashboard_data(products)

        self.assertEqual(summary["products_count"], 2)
        self.assertEqual(summary["units_count"], 10)
        self.assertEqual(summary["categories_count"], 2)
        self.assertEqual(summary["alerts_count"], 1)
        self.assertEqual([item["nombre"] for item in summary["expiring_products"]], ["Arroz"])


class TokenTests(unittest.TestCase):
    def test_access_token_round_trip(self):
        token = create_access_token("usuario-prueba")

        self.assertEqual(decode_access_token(token), "usuario-prueba")
        self.assertIsNone(decode_access_token("token-invalido"))


class DatabaseConfigurationTests(unittest.TestCase):
    @patch.dict(
        "os.environ",
        {
            "NOTVENCE_DB_HOST": "mysql.example.com",
            "NOTVENCE_DB_USER": "test-user",
            "NOTVENCE_DB_PASSWORD": "test-password",
            "NOTVENCE_DB_NAME": "test-db",
            "NOTVENCE_DB_PORT": "3307",
            "NOTVENCE_DB_SSL_CA": "ca.pem",
        },
        clear=True,
    )
    @patch("app.database.mysql.connector.connect")
    def test_connection_uses_environment_and_verifies_configured_tls(
        self, connect
    ):
        get_connection()

        connect.assert_called_once_with(
            host="mysql.example.com",
            user="test-user",
            password="test-password",
            database="test-db",
            port=3307,
            ssl_ca="ca.pem",
            ssl_verify_cert=True,
            ssl_verify_identity=True,
        )

    @patch.dict("os.environ", {}, clear=True)
    def test_connection_requires_database_credentials(self):
        with self.assertRaisesRegex(RuntimeError, "NOTVENCE_DB_USER"):
            get_connection()


class PasswordHashTests(unittest.TestCase):
    def test_password_hash_is_not_reversible_and_verifies_correctly(self):
        stored = hash_password("Password123")

        self.assertTrue(stored.startswith("$argon2id$"))
        self.assertNotEqual(stored, "Password123")
        self.assertEqual(verify_password_and_update("Password123", stored), (True, None))
        self.assertEqual(verify_password_and_update("incorrecta", stored), (False, None))

    def test_legacy_plain_text_is_upgraded_after_successful_verification(self):
        valid, replacement = verify_password_and_update("Password123", "Password123")

        self.assertTrue(valid)
        self.assertIsNotNone(replacement)
        self.assertNotEqual(replacement, "Password123")
        self.assertEqual(
            verify_password_and_update("Password123", replacement),
            (True, None),
        )

    def test_malformed_hash_is_rejected(self):
        self.assertEqual(
            verify_password_and_update("Password123", "$argon2id$broken"),
            (False, None),
        )


if __name__ == "__main__":
    unittest.main()
