import pytest
from harbor.models.trial.error_policy import policy_for

from agentclinic.agents.errors import (
    AgentAuthenticationError,
    ApiConnectionError,
    RuntimeRequestError,
)


@pytest.mark.parametrize("error", [RuntimeRequestError, ApiConnectionError, AgentAuthenticationError])
def test_agent_infrastructure_errors_never_count_as_valid_rewards(error):
    assert policy_for(error.__name__).has_valid_reward is False


def test_clinic_failures_skip_grading():
    assert policy_for(RuntimeRequestError.__name__).should_grade is False
