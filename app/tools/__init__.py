from app.tools.datetime import get_current_datetime
from app.tools.feedback import leave_feedback
from app.tools.location import get_current_location
from app.tools.places import (
    check_place_hours,
    find_nearby_places,
    get_place_details,
    search_places,
)

ALL_TOOLS = [
    get_current_datetime,
    get_current_location,
    search_places,
    get_place_details,
    find_nearby_places,
    check_place_hours,
    leave_feedback,
]
