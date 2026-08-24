use std::collections::HashMap;

use tokio::time::Instant;

use crate::domain::{
    profiler::ProfilerError,
    providers::{ProviderError, ProviderId, ProviderRequestState},
};

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct RequestId(usize);

impl RequestId {
    pub const fn new(value: usize) -> Self {
        Self(value)
    }
    pub const fn index(self) -> usize {
        self.0
    }

    pub fn next(self) -> Self {
        Self(self.0.checked_add(1).expect("request ID space exhausted"))
    }
}

struct ProviderRequestRecord {
    providers: HashMap<ProviderId, ProviderRequestState>,
    deadline: Instant,
}

pub(crate) struct RequestsState {
    requests: HashMap<RequestId, ProviderRequestRecord>,
    last_issued_request_id: Option<RequestId>,
}

impl RequestsState {
    pub(crate) fn new(request_capacity: usize) -> Self {
        Self {
            requests: HashMap::with_capacity(request_capacity),
            last_issued_request_id: None,
        }
    }

    pub(crate) fn issue_request_id(&mut self) -> RequestId {
        let request_id = self
            .last_issued_request_id
            .map_or(RequestId::new(0), RequestId::next);

        self.last_issued_request_id = Some(request_id);
        request_id
    }

    pub(crate) fn record_request(
        &mut self,
        request_id: RequestId,
        providers: HashMap<ProviderId, ProviderRequestState>,
        deadline: Instant,
    ) {
        let replaced = self.requests.insert(
            request_id,
            ProviderRequestRecord {
                providers,
                deadline,
            },
        );

        debug_assert!(replaced.is_none());
    }

    pub(crate) fn provider_is_pending(
        &self,
        request_id: RequestId,
        provider_id: ProviderId,
    ) -> Result<bool, ProfilerError> {
        let request = self
            .requests
            .get(&request_id)
            .ok_or(ProfilerError::UnknownRequest(request_id))?;

        let state =
            request
                .providers
                .get(&provider_id)
                .ok_or(ProfilerError::UnknownRequestProvider {
                    request_id,
                    provider_id,
                })?;

        Ok(matches!(state, ProviderRequestState::Pending))
    }

    pub(crate) fn set_provider_success(
        &mut self,
        request_id: RequestId,
        provider_id: ProviderId,
    ) -> Result<(), ProfilerError> {
        let state = self.provider_state_mut(request_id, provider_id)?;

        if matches!(state, ProviderRequestState::Pending) {
            *state = ProviderRequestState::Succeeded;
        }

        Ok(())
    }

    pub(crate) fn set_provider_failure(
        &mut self,
        request_id: RequestId,
        provider_id: ProviderId,
        error: ProviderError,
    ) -> Result<(), ProfilerError> {
        let state = self.provider_state_mut(request_id, provider_id)?;

        if matches!(state, ProviderRequestState::Pending) {
            *state = ProviderRequestState::Failed(error);
        }

        Ok(())
    }

    fn provider_state_mut(
        &mut self,
        request_id: RequestId,
        provider_id: ProviderId,
    ) -> Result<&mut ProviderRequestState, ProfilerError> {
        self.requests
            .get_mut(&request_id)
            .ok_or(ProfilerError::UnknownRequest(request_id))?
            .providers
            .get_mut(&provider_id)
            .ok_or(ProfilerError::UnknownRequestProvider {
                request_id,
                provider_id,
            })
    }

    pub(crate) fn is_finished(&self, request_id: RequestId) -> Result<bool, ProfilerError> {
        let request = self
            .requests
            .get(&request_id)
            .ok_or(ProfilerError::UnknownRequest(request_id))?;

        Ok(request
            .providers
            .values()
            .all(|state| !matches!(state, ProviderRequestState::Pending)))
    }

    pub(crate) fn first_failure(&self, request_id: RequestId) -> Option<ProviderError> {
        self.requests
            .get(&request_id)?
            .providers
            .values()
            .find_map(|state| match state {
                ProviderRequestState::Failed(error) => Some(error.clone()),
                ProviderRequestState::Pending | ProviderRequestState::Succeeded => None,
            })
    }

    pub(crate) fn expire(&mut self, now: Instant) -> Vec<RequestId> {
        let mut expired = Vec::new();

        for (request_id, request) in &mut self.requests {
            if request.deadline > now {
                continue;
            }

            let mut changed = false;

            for (provider_id, state) in &mut request.providers {
                if matches!(state, ProviderRequestState::Pending) {
                    *state = ProviderRequestState::Failed(ProviderError::RequestTimedOut {
                        provider_id: *provider_id,
                        request_id: *request_id,
                    });
                    changed = true;
                }
            }

            if changed {
                expired.push(*request_id);
            }
        }

        expired
    }

    pub(crate) fn next_deadline(&self) -> Option<Instant> {
        self.requests
            .values()
            .filter(|request| {
                request
                    .providers
                    .values()
                    .any(|state| matches!(state, ProviderRequestState::Pending))
            })
            .map(|request| request.deadline)
            .min()
    }

    pub(crate) fn is_retired(&self, request_id: RequestId) -> bool {
        !self.requests.contains_key(&request_id)
            && self
                .last_issued_request_id
                .is_some_and(|last_issued| request_id <= last_issued)
    }

    pub(crate) fn clear(&mut self, request_id: RequestId) {
        self.requests.remove(&request_id);
    }
}
