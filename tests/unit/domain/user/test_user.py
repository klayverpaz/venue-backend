from app.domain.user.user import User


def test_cria_user_valido():
    r = User.create(
        name="João Silva",
        email="JOAO@EXEMPLO.com",
        phone="(21) 99694-9389",
        credit_score=85,
        balance=1500.50,
    )
    assert r.is_success, r.error
    u = r.value
    assert u.name == "João Silva"
    assert u.email.value == "joao@exemplo.com"
    assert u.phone.value == "+5521996949389"
    assert u.credit_score.value == 85.0
    assert u.balance.value == 1500.50


def test_rejeita_name_vazio():
    r = User.create(name="  ", email="a@b.com", phone="(21) 99694-9389")
    assert r.is_failure
    assert "name" in r.error


def test_agrega_erros_de_multiplos_vos():
    r = User.create(
        name="X",
        email="invalido",
        phone="00 00000 0000",
        credit_score=150,
        balance=-10,
    )
    assert r.is_failure
    err = r.error.lower()
    assert "email" in err
    assert "phone" in err or "brazilianphone" in err
    assert "percentage" in err or "credit" in err or "score" in err[:200]
    assert "negativ" in err


def test_change_email_valida_novo_email():
    u = User.create(name="X", email="a@b.com", phone="(21) 99694-9389").value
    old_updated = u.updated_at
    r = u.change_email("NEW@x.com")
    assert r.is_success
    assert u.email.value == "new@x.com"
    assert u.updated_at >= old_updated


def test_change_email_rejeita_invalido():
    u = User.create(name="X", email="a@b.com", phone="(21) 99694-9389").value
    r = u.change_email("not-an-email")
    assert r.is_failure
    assert u.email.value == "a@b.com"  # inalterado
