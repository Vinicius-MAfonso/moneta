from ninja import Router
from .schemas import UserProfileOut, UserProfileUpdateIn

router = Router(tags=["Users"])


@router.get("/me", response=UserProfileOut)
def get_user_profile(request):
    return request.user


@router.put("/me", response=UserProfileOut)
def update_user_profile(request, payload: UserProfileUpdateIn):
    user = request.user
    if payload.first_name is not None:
        user.first_name = payload.first_name
    if payload.last_name is not None:
        user.last_name = payload.last_name
    if payload.email is not None:
        user.email = payload.email
    if payload.photo_url is not None:
        user.photo_url = payload.photo_url
    if payload.currency is not None:
        user.currency = payload.currency
    if payload.timezone is not None:
        user.timezone = payload.timezone
    user.save()
    return user
