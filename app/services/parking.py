from typing import Any, Dict, Optional

from app.services.identity import TrustedIdentity, is_well_formed_identity
from app.services.policy import district_scope_for_identity, role_allows_action


class MockParkingService:
    """Mock domain service for city parking operations with synthetic district records.

    CRITICAL INVARIANT: This service represents a protected domain resource.
    It MUST NOT be called directly before authorization has completed and returned Decision.ALLOW.
    """

    def __init__(self):
        self.call_count = 0
        self.records: Dict[str, Dict[str, Any]] = {
            # District North records
            "park_north_1": {
                "resource_id": "park_north_1",
                "district_id": "district_north",
                "name": "North Central Parking",
                "total_spots": 120,
                "available_spots": 45,
                "status": "open",
            },
            "park_north_2": {
                "resource_id": "park_north_2",
                "district_id": "district_north",
                "name": "North Metro Lot",
                "total_spots": 200,
                "available_spots": 110,
                "status": "open",
            },
            # District South records
            "park_south_1": {
                "resource_id": "park_south_1",
                "district_id": "district_south",
                "name": "South Port Garage",
                "total_spots": 150,
                "available_spots": 20,
                "status": "open",
            },
            "park_south_2": {
                "resource_id": "park_south_2",
                "district_id": "district_south",
                "name": "South Bay Deck",
                "total_spots": 80,
                "available_spots": 5,
                "status": "open",
            },
        }

    def get_resource(self, resource_id: str) -> Optional[Dict[str, Any]]:
        """Return a copy of the authoritative resource record, if it exists.

        This lookup is metadata resolution only; it does not execute an
        operation and therefore does not increment ``call_count``.
        """
        record = self.records.get(resource_id)
        if not isinstance(record, dict):
            return None
        if record.get("resource_id") != resource_id:
            return None
        return dict(record)

    def execute(
        self,
        operation: str,
        resource_id: str,
        *,
        authorized_identity: Optional[TrustedIdentity] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute a protected operation on a parking resource.

        Called by GatewayService only after policy evaluation confirms
        ``Decision.ALLOW``. The identity and authoritative record checks here
        are intentional defense in depth so a caller cannot bypass district
        isolation by invoking the service with an incorrect earlier decision.
        """
        self.call_count += 1
        record = self.records.get(resource_id)
        if not record:
            return {
                "success": False,
                "error": f"Parking resource '{resource_id}' not found",
                "reason_code": "RESOURCE_NOT_FOUND",
            }

        if (
            authorized_identity is None
            or not is_well_formed_identity(authorized_identity)
            or not authorized_identity.is_authenticated
        ):
            return {
                "success": False,
                "error": "Authenticated authorization context is required",
                "reason_code": "UNAUTHENTICATED_ACTOR",
            }

        if not role_allows_action(authorized_identity.role, "parking", operation):
            return {
                "success": False,
                "error": "Role is not authorized for the requested operation",
                "reason_code": "ROLE_NOT_AUTHORIZED",
            }

        actual_district_id = record.get("district_id")
        if not isinstance(actual_district_id, str) or not actual_district_id.strip():
            return {
                "success": False,
                "error": f"Parking resource '{resource_id}' has invalid district metadata",
                "reason_code": "INVALID_RESOURCE_DISTRICT",
            }

        district_scope = district_scope_for_identity(authorized_identity)
        if district_scope is not None and actual_district_id != district_scope:
            return {
                "success": False,
                "error": (
                    f"Identity district '{district_scope}' does not match "
                    f"resource district '{actual_district_id}'"
                ),
                "reason_code": "DISTRICT_MISMATCH",
            }

        if operation in ("read", "status"):
            return {
                "success": True,
                "operation": operation,
                "record": dict(record),
            }

        if operation == "reserve_spot":
            if record["available_spots"] > 0:
                record["available_spots"] -= 1
                return {
                    "success": True,
                    "operation": operation,
                    "resource_id": resource_id,
                    "available_spots": record["available_spots"],
                    "status": "reserved",
                }
            return {
                "success": False,
                "operation": operation,
                "resource_id": resource_id,
                "error": "No spots available",
                "status": "full",
            }

        if operation == "release_spot":
            if record["available_spots"] < record["total_spots"]:
                record["available_spots"] += 1
                return {
                    "success": True,
                    "operation": operation,
                    "resource_id": resource_id,
                    "available_spots": record["available_spots"],
                    "status": "released",
                }
            return {
                "success": False,
                "operation": operation,
                "resource_id": resource_id,
                "error": "Cannot exceed total capacity",
            }

        return {
            "success": True,
            "operation": operation,
            "resource_id": resource_id,
            "status": "executed",
        }
