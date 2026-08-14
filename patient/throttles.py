import sys

from rest_framework.throttling import UserRateThrottle

_TESTING = "test" in sys.argv


class PatientChatThrottle(UserRateThrottle):
    scope = "patient_chat"

    def allow_request(self, request, view):
        if _TESTING:
            return True
        return super().allow_request(request, view)


class PatientSummaryThrottle(UserRateThrottle):
    scope = "patient_summary"

    def allow_request(self, request, view):
        if _TESTING:
            return True
        return super().allow_request(request, view)
