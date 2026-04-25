from app.use_cases.users.dtos import UserDto
from app.domain.user.user import User


def test_user_dto_from_entity():
    u = User.create(
        name="A", email="a@x.com", phone="(21) 99694-9389",
        credit_score=75, balance=100.50,
    ).value
    d = UserDto.from_entity(u)
    assert d.id == u.id
    assert d.email == "a@x.com"
    assert d.phone == "+5521996949389"
    assert d.phone_display == "(21) 99694-9389"
    assert d.credit_score == 75.0
    assert d.balance == 100.50
