import unittest
from copy import deepcopy
from datetime import date, timedelta
import sys
from types import ModuleType
from unittest.mock import Mock, call, patch

from fastapi.testclient import TestClient

from app.auth import create_access_token, decode_access_token
from app.deps import get_current_user_casa
from app.passwords import verify_password_and_update

notification_stub = ModuleType("app.notificaciones")
notification_stub.enviar_aviso = lambda **kwargs: None
sys.modules.setdefault("app.notificaciones", notification_stub)

from app.main import app
from app.store import CUSTOM_SHOPPING_ITEMS, SHOPPING_ITEMS, SHOPPING_REMOVED


def product_fixture(**changes):
    product = {
        "codigo": "NV-001",
        "nombre": "Arroz",
        "categoria": "Alimentos",
        "subcategoria": "Granos",
        "presentacion": "Kg",
        "cantidad": 5,
        "stock_minimo": 3,
        "ubicacion": "Despensa",
        "vence": (date.today() + timedelta(days=2)).isoformat(),
        "alertas": [],
        "estado": "Activo",
        "estado_clase": "success",
    }
    product.update(changes)
    return product


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.original_custom_items = deepcopy(CUSTOM_SHOPPING_ITEMS)
        self.original_shopping_items = deepcopy(SHOPPING_ITEMS)
        self.original_removed_items = set(SHOPPING_REMOVED)
        app.dependency_overrides[get_current_user_casa] = lambda: ("tester", 7)
        self.client = TestClient(app, follow_redirects=False)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.pop(get_current_user_casa, None)
        CUSTOM_SHOPPING_ITEMS.clear()
        CUSTOM_SHOPPING_ITEMS.update(self.original_custom_items)
        SHOPPING_ITEMS.clear()
        SHOPPING_ITEMS.update(self.original_shopping_items)
        SHOPPING_REMOVED.clear()
        SHOPPING_REMOVED.update(self.original_removed_items)

    def test_api_rejects_requests_without_authentication(self):
        app.dependency_overrides.pop(get_current_user_casa, None)

        response = self.client.get("/api/productos")

        self.assertEqual(response.status_code, 401)

    def test_health_endpoint_does_not_require_database(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    @patch("app.api.auth.get_connection")
    def test_login_returns_access_token_for_valid_credentials(self, get_connection):
        cursor = Mock()
        cursor.fetchone.return_value = (19, "tester", "Password123")
        connection = get_connection.return_value
        connection.cursor.return_value = cursor

        response = self.client.post(
            "/api/auth/login",
            json={"username": "tester", "password": "Password123"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(decode_access_token(response.json()["access_token"]), "tester")
        replacement_hash = cursor.execute.call_args_list[1].args[1][0]
        self.assertTrue(verify_password_and_update("Password123", replacement_hash)[0])

    @patch("app.api.auth.get_connection")
    def test_registration_stores_password_hash(self, get_connection):
        cursor = Mock()
        cursor.fetchone.side_effect = [None, None]
        cursor.lastrowid = 32
        get_connection.return_value.cursor.return_value = cursor

        response = self.client.post(
            "/api/auth/register",
            json={
                "username": "tester",
                "email": "tester@example.com",
                "password": "Password123",
            },
        )

        self.assertEqual(response.status_code, 201)
        stored_hash = cursor.execute.call_args_list[-1].args[1][3]
        self.assertNotEqual(stored_hash, "Password123")
        self.assertTrue(verify_password_and_update("Password123", stored_hash)[0])

    @patch("app.api.auth.get_connection")
    def test_login_rejects_invalid_credentials(self, get_connection):
        cursor = Mock()
        cursor.fetchone.return_value = None
        get_connection.return_value.cursor.return_value = cursor

        response = self.client.post(
            "/api/auth/login",
            json={"username": "tester", "password": "wrong"},
        )

        self.assertEqual(response.status_code, 401)

    @patch("app.api.auth.get_connection")
    def test_registration_rejects_weak_password_without_database_access(
        self, get_connection
    ):
        response = self.client.post(
            "/api/auth/register",
            json={
                "username": "tester",
                "email": "tester@example.com",
                "password": "weak",
            },
        )

        self.assertEqual(response.status_code, 400)
        get_connection.assert_not_called()

    @patch("app.main.products_repo.get_connection")
    def test_web_registration_stores_password_hash(self, get_connection):
        cursor = Mock()
        cursor.fetchone.return_value = None
        cursor.lastrowid = 33
        get_connection.return_value.cursor.return_value = cursor

        response = self.client.post(
            "/registro",
            data={
                "username": "tester",
                "email": "tester@example.com",
                "password": "Password123",
            },
        )

        self.assertEqual(response.status_code, 303)
        stored_hash = cursor.execute.call_args_list[-1].args[1][3]
        self.assertNotEqual(stored_hash, "Password123")
        self.assertTrue(verify_password_and_update("Password123", stored_hash)[0])

    @patch("app.main.products_repo.get_connection")
    def test_web_login_upgrades_legacy_password_and_sets_session(self, get_connection):
        cursor = Mock()
        cursor.fetchone.return_value = (19, "tester", "Password123")
        get_connection.return_value.cursor.return_value = cursor

        response = self.client.post(
            "/login",
            data={"username": "tester", "password": "Password123"},
        )

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/dashboard")
        self.assertIn("notvence_user=tester", response.headers["set-cookie"])
        replacement_hash = cursor.execute.call_args_list[1].args[1][0]
        self.assertTrue(verify_password_and_update("Password123", replacement_hash)[0])

    @patch("app.api.productos.products_repo.list_products")
    def test_product_list_filters_by_name_and_category(self, list_products):
        list_products.return_value = [
            product_fixture(),
            product_fixture(codigo="NV-002", nombre="Jugo", categoria="Bebidas"),
        ]

        response = self.client.get("/api/productos?q=arroz&categoria=Alimentos")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["codigo"] for item in response.json()], ["NV-001"])
        list_products.assert_called_once_with(7)

    def test_product_creation_rejects_invalid_expiry(self):
        response = self.client.post(
            "/api/productos",
            json={
                "nombre": "Leche",
                "categoria": "Alimentos",
                "presentacion": "Litro",
                "cantidad": 1,
                "ubicacion": "Nevera",
                "vence": "2030-02-30",
            },
        )

        self.assertEqual(response.status_code, 422)

    @patch("app.api.productos.enviar_alertas_producto")
    @patch("app.api.productos.products_repo.create_product")
    def test_product_creation_saves_payload_and_returns_product(
        self, create_product, send_alerts
    ):
        created = product_fixture(nombre="Leche", cantidad=2)
        create_product.return_value = created

        response = self.client.post(
            "/api/productos",
            json={
                "nombre": "Leche",
                "categoria": "Alimentos",
                "presentacion": "Litro",
                "cantidad": 2,
                "stock_minimo": 3,
                "ubicacion": "Nevera",
                "vence": created["vence"],
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["nombre"], "Leche")
        self.assertEqual(create_product.call_args.args[1], 7)
        self.assertEqual(create_product.call_args.args[0]["cantidad"], 2)
        send_alerts.assert_called_once()

    @patch("app.api.productos.products_repo.update_product")
    def test_product_update_returns_not_found_for_missing_product(self, update_product):
        update_product.return_value = None

        response = self.client.put(
            "/api/productos/NV-404",
            json={
                "nombre": "Arroz",
                "categoria": "Alimentos",
                "presentacion": "Kg",
                "cantidad": 5,
                "ubicacion": "Despensa",
            },
        )

        self.assertEqual(response.status_code, 404)

    @patch("app.api.productos.products_repo.delete_product")
    def test_product_delete_returns_no_content(self, delete_product):
        delete_product.return_value = True

        response = self.client.delete("/api/productos/NV-001")

        self.assertEqual(response.status_code, 204)
        delete_product.assert_called_once_with("NV-001", 7)

    @patch("app.api.movimientos.movimientos_repo.create_movement", return_value=42)
    @patch("app.api.movimientos.products_repo._codigo_to_id", return_value=9)
    @patch("app.api.movimientos.products_repo.update_product")
    @patch("app.api.movimientos.products_repo.get_product")
    def test_movement_updates_inventory_quantity(
        self, get_product, update_product, code_to_id, create_movement
    ):
        get_product.return_value = product_fixture(cantidad=5)

        response = self.client.post(
            "/api/movimientos",
            json={"codigo": "NV-001", "tipo": "Consumo", "cantidad": 2},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["id_movimiento"], 42)
        self.assertEqual(update_product.call_args.args[1]["cantidad"], 3)
        create_movement.assert_called_once_with(9, "Consumo", 2)

    @patch("app.api.movimientos.products_repo.get_product")
    def test_movement_rejects_consumption_above_available_stock(self, get_product):
        get_product.return_value = product_fixture(cantidad=2)

        response = self.client.post(
            "/api/movimientos",
            json={"codigo": "NV-001", "tipo": "Consumo", "cantidad": 3},
        )

        self.assertEqual(response.status_code, 400)

    def test_movement_rejects_zero_quantity(self):
        response = self.client.post(
            "/api/movimientos",
            json={"codigo": "NV-001", "tipo": "Entrada", "cantidad": 0},
        )

        self.assertEqual(response.status_code, 422)

    def test_shopping_list_custom_item_lifecycle(self):
        created = self.client.post(
            "/api/lista-compra",
            json={"nombre": "Pilas", "cantidad": 2},
        )

        self.assertEqual(created.status_code, 201)
        item = created.json()
        self.assertTrue(item["personalizado"])
        self.assertEqual(item["compra_cantidad"], 2)

        updated = self.client.put(
            f"/api/lista-compra/{item['codigo']}",
            json={"cantidad_compra": 4, "comprado": True},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["compra_cantidad"], 4)
        self.assertTrue(updated.json()["comprado"])

        deleted = self.client.delete(f"/api/lista-compra/{item['codigo']}")
        self.assertEqual(deleted.status_code, 204)

    @patch("app.api.categorias.catalog_options")
    def test_categories_endpoint_requires_auth_and_returns_options(self, catalog_options):
        catalog_options.return_value = {
            "Alimentos": {"presentaciones": ["Kg"], "subcategorias": ["Granos"]}
        }

        response = self.client.get(
            "/api/categorias/Alimentos/subcategorias",
            headers={"Authorization": f"Bearer {create_access_token('tester')}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["subcategorias"], ["Granos"])

    @patch("app.products_repo.list_products")
    def test_dashboard_and_alerts_use_house_inventory(self, list_products):
        expiring = product_fixture(
            cantidad=1,
            estado="Stock bajo",
            estado_clase="danger",
            alertas=["Stock bajo", "Por vencer"],
        )
        list_products.return_value = [expiring]

        dashboard = self.client.get("/api/dashboard")
        alerts = self.client.get("/api/alertas")

        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.json()["products_count"], 1)
        self.assertEqual(dashboard.json()["alerts_count"], 1)
        self.assertEqual(alerts.status_code, 200)
        self.assertEqual(alerts.json()[0]["codigo"], "NV-001")
        self.assertEqual(list_products.call_args_list, [call(7), call(7)])


if __name__ == "__main__":
    unittest.main()
