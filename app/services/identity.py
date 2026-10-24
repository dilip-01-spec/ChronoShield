from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class TrustedIdentity:
    """Server-verified identity used for policy evaluation and authorization."""
    user_id: str
    role: str
    district_id: str
    is_authenticated: bool = True


def is_well_formed_identity(identity: object) -> bool:
    """Validate identity fields without granting permissions or coercing values.

    Role membership (including empty strings) is checked by the policy allowlist.
    A boolean False remains valid for the existing non-executing preview flow.
    """
    return (
        isinstance(identity, TrustedIdentity)
        and isinstance(getattr(identity, "role", None), str)
        and isinstance(getattr(identity, "is_authenticated", None), bool)
        and all(
            isinstance(value, str) and bool(value.strip())
            for value in (
                getattr(identity, "user_id", None),
                getattr(identity, "district_id", None),
            )
        )
    )


class IdentityResolver:
    """Resolves caller identity from a trusted server-side store.

    SECURITY RULE: Client-supplied roles in ActorContext must NEVER be trusted.
    An unauthenticated request supplying a known user_id is NOT proof of identity.
    Proof requires a verified token/credential.
    """

    DEMO_USERS = {
        "user_admin": TrustedIdentity(
            user_id="user_admin",
            role="admin",
            district_id="district_central",
            is_authenticated=True,
        ),
        "user_operator_north": TrustedIdentity(
            user_id="user_operator_north",
            role="operator",
            district_id="district_north",
            is_authenticated=True,
        ),
        "user_operator_south": TrustedIdentity(
            user_id="user_operator_south",
            role="operator",
            district_id="district_south",
            is_authenticated=True,
        ),
        "user_viewer": TrustedIdentity(
            user_id="user_viewer",
            role="viewer",
            district_id="district_central",
            is_authenticated=True,
        ),
    }

    # Verified credentials / bearer tokens for demo authentication
    DEMO_TOKENS = {
        "token_admin": TrustedIdentity(
            user_id="user_admin",
            role="admin",
            district_id="district_central",
            is_authenticated=True,
        ),
        "token_operator_north": TrustedIdentity(
            user_id="user_operator_north",
            role="operator",
            district_id="district_north",
            is_authenticated=True,
        ),
        "token_operator_south": TrustedIdentity(
            user_id="user_operator_south",
            role="operator",
            district_id="district_south",
            is_authenticated=True,
        ),
        "token_viewer": TrustedIdentity(
            user_id="user_viewer",
            role="viewer",
            district_id="district_central",
            is_authenticated=True,
        ),
    }

    def resolve(
        self,
        auth_token: Optional[str] = None,
        actor_user_id: Optional[str] = None,
    ) -> Optional[TrustedIdentity]:
        """Resolve identity from authenticated token or unauthenticated actor metadata.

        If authenticated with auth_token -> returns TrustedIdentity(is_authenticated=True).
        If only actor_user_id is supplied without token -> returns TrustedIdentity(is_authenticated=False).
        An unauthenticated identity can preview policy decisions, but CANNOT execute protected services.
        """
        # 1. Check for token-based authentication proof
        if auth_token:
            token = auth_token.strip()
            if token.lower().startswith("bearer "):
                token = token[7:].strip()
            return self.DEMO_TOKENS.get(token)

        # 2. Unauthenticated request with client-supplied actor metadata
        if actor_user_id:
            user = self.DEMO_USERS.get(actor_user_id)
            if user:
                return TrustedIdentity(
                    user_id=user.user_id,
                    role=user.role,
                    district_id=user.district_id,
                    is_authenticated=False,  # Unauthenticated request: NOT proof of identity
                )

        return None
