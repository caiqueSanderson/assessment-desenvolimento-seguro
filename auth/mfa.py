SIMULATED_MFA_CODE = "123456"


def verify_mfa_code(code: str | None) -> bool:
    return code == SIMULATED_MFA_CODE