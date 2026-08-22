from __future__ import annotations

import dataclasses
import types
import typing

from tools.profiler import schema, wall_critical_path, wall_model


def _sample(
    identity: wall_model.ThreadIdentity,
    observation_index: int,
    start_ns: int,
    end_ns: int,
    state: str,
    stack: tuple[int, ...],
) -> wall_model.ThreadSample:
    return wall_model.ThreadSample(
        observation=wall_model.ObservationSample(
            observation_index=observation_index,
            interval=wall_model.Interval(start_ns, end_ns),
        ),
        identity=identity,
        pre_stop_state=state,
        stack=stack,
    )


def _samples(
    *observations: dict[wall_model.ThreadIdentity, wall_model.ThreadSample],
) -> wall_model.Samples:
    by_identity: dict[wall_model.ThreadIdentity, list[wall_model.ThreadSample]] = {}
    observation_samples: list[wall_model.ObservationSample] = []
    for observation in observations:
        first_sample = next(iter(observation.values()), None)
        if first_sample is None:
            continue
        observation_sample = wall_model.ObservationSample(
            first_sample.observation_index,
            first_sample.interval,
        )
        for identity, sample in observation.items():
            sample = dataclasses.replace(sample, observation=observation_sample)
            observation_sample.threads[identity] = sample
            by_identity.setdefault(identity, []).append(sample)
        observation_samples.append(observation_sample)
    return wall_model.Samples(observation_samples, by_identity)


def _profile_with_observation_times(*target_running_times: int) -> schema.RawProfile:
    observations = [
        {"target_running_ns": target_running_ns}
        for target_running_ns in target_running_times
    ]
    return typing.cast(
        "schema.RawProfile",
        typing.cast("object", types.SimpleNamespace(observations=observations)),
    )


# PRF-047: Multi-threaded critical path.
def test_wait_start_reaches_the_first_observation():
    downstream = wall_model.ThreadIdentity(11, 101)
    producer = wall_model.ThreadIdentity(12, 102)
    first_wait = _sample(downstream, 0, 0, 10, "S", (1,))
    second_wait = _sample(downstream, 1, 10, 20, "S", (1,))
    producer_work = _sample(producer, 1, 10, 20, "R", (2,))
    downstream_work = _sample(downstream, 2, 20, 30, "R", (1,))

    transitions = wall_critical_path._transitions(  # pyright: ignore[reportPrivateUsage]
        _profile_with_observation_times(5, 15, 25),
        _samples(
            {downstream: first_wait},
            {downstream: second_wait, producer: producer_work},
            {downstream: downstream_work},
        ),
    )

    assert transitions[downstream][0].downstream_wait_ns == 20


# PRF-047: Multi-threaded critical path.
def test_departed_candidate_uses_its_latest_working_sample():
    downstream = wall_model.ThreadIdentity(11, 101)
    producer = wall_model.ThreadIdentity(12, 102)
    first_producer_sample = _sample(producer, 0, 0, 10, "R", (1,))
    latest_producer_sample = _sample(producer, 1, 10, 20, "R", (2,))
    departed_candidates = wall_critical_path._departed_working_candidates  # pyright: ignore[reportPrivateUsage]

    candidates = departed_candidates(
        downstream,
        0,
        1,
        {downstream: _sample(downstream, 2, 20, 30, "R", (3,))},
        {producer: [first_producer_sample, latest_producer_sample]},
    )

    assert candidates == [latest_producer_sample]


def test_departed_candidates_exclude_work_before_wait_and_after_transition():
    downstream = wall_model.ThreadIdentity(11, 101)
    earlier_producer = wall_model.ThreadIdentity(12, 102)
    later_producer = wall_model.ThreadIdentity(13, 103)
    departed_candidates = wall_critical_path._departed_working_candidates  # pyright: ignore[reportPrivateUsage]

    candidates = departed_candidates(
        downstream,
        1,
        1,
        {downstream: _sample(downstream, 2, 20, 30, "R", (3,))},
        {
            earlier_producer: [_sample(earlier_producer, 0, 0, 10, "R", (1,))],
            later_producer: [_sample(later_producer, 2, 20, 30, "R", (2,))],
        },
    )

    assert candidates == []


# PRF-047: Multi-threaded critical path.
def test_new_worker_uses_the_prior_stack_bearing_candidate():
    producer = wall_model.ThreadIdentity(11, 101)
    downstream = wall_model.ThreadIdentity(12, 102)
    producer_before = _sample(producer, 0, 0, 10, "R", (1,))
    producer_after = _sample(producer, 1, 10, 20, "R", (1,))
    downstream_after = _sample(downstream, 1, 10, 20, "R", (2,))
    transitions_for = wall_critical_path._transitions  # pyright: ignore[reportPrivateUsage]

    transitions = transitions_for(
        _profile_with_observation_times(5, 15),
        _samples(
            {producer: producer_before},
            {
                producer: producer_after,
                downstream: downstream_after,
            },
        ),
    )

    assert len(transitions) == 1
    transition = transitions[downstream][0]
    assert transition.target_running_ns == 10
    assert transition.downstream_sample == downstream_after
    assert transition.downstream_wait_ns == 0
    assert transition.downstream_first_observed is True
    assert transition.candidates == (producer_before,)


# PRF-047: Multi-threaded critical path.
def test_new_waiting_worker_uses_the_prior_stack_bearing_candidate():
    producer = wall_model.ThreadIdentity(11, 101)
    downstream = wall_model.ThreadIdentity(12, 102)
    producer_before = _sample(producer, 0, 0, 10, "R", (1,))
    downstream_after = _sample(downstream, 1, 10, 20, "S", (2,))
    transitions_for = wall_critical_path._transitions  # pyright: ignore[reportPrivateUsage]

    transitions = transitions_for(
        _profile_with_observation_times(5, 15),
        _samples({producer: producer_before}, {downstream: downstream_after}),
    )

    assert len(transitions) == 1
    transition = transitions[downstream][0]
    assert transition.target_running_ns == 10
    assert transition.downstream_sample == downstream_after
    assert transition.downstream_wait_ns == 0
    assert transition.candidates == (producer_before,)


# PRF-052: Independent causal evidence.
def test_scheduler_wake_resolves_an_ambiguous_sampled_transition():
    producer = wall_model.ThreadIdentity(11, 101)
    competing_worker = wall_model.ThreadIdentity(12, 102)
    downstream = wall_model.ThreadIdentity(13, 103)
    producer_before = _sample(producer, 0, 0, 10, "R", (1,))
    competing_before = _sample(competing_worker, 0, 0, 10, "R", (2,))
    downstream_after = _sample(downstream, 1, 10, 20, "R", (3,))
    samples = _samples(
        {
            producer: producer_before,
            competing_worker: competing_before,
        },
        {downstream: downstream_after},
    )
    samples.scheduler_wakes.append(
        wall_model.SchedulerWake(
            kind="wakeup-new",
            target_running_ns=8,
            upstream_os_thread_id=producer.os_thread_id,
            downstream_os_thread_id=downstream.os_thread_id,
        )
    )

    transitions = wall_critical_path._transitions(  # pyright: ignore[reportPrivateUsage]
        _profile_with_observation_times(5, 15),
        samples,
    )

    transition = transitions[downstream][0]
    assert transition.target_running_ns == 8
    assert transition.candidates == (producer_before,)
    assert transition.evidence == "scheduler-wake"


# PRF-052: Independent causal evidence.
def test_scheduler_wake_at_interval_start_belongs_to_the_prior_transition():
    downstream = wall_model.ThreadIdentity(13, 103)
    scheduler_wake_candidate = wall_critical_path._scheduler_wake_candidate  # pyright: ignore[reportPrivateUsage]

    wake, candidate = scheduler_wake_candidate(
        {
            downstream.os_thread_id: [
                wall_model.SchedulerWake(
                    kind="waking",
                    target_running_ns=5,
                    upstream_os_thread_id=11,
                    downstream_os_thread_id=downstream.os_thread_id,
                )
            ]
        },
        {},
        downstream,
        wall_model.Interval(5, 10),
    )

    assert wake is None
    assert candidate is None


# PRF-047: Multi-threaded critical path.
def test_latest_transition_can_include_an_exact_phase_boundary():
    downstream = wall_model.ThreadIdentity(12, 102)
    transition_type = wall_critical_path._Transition  # pyright: ignore[reportPrivateUsage]
    latest_transition = wall_critical_path._latest_transition  # pyright: ignore[reportPrivateUsage]
    downstream_sample = _sample(downstream, 1, 10, 20, "R", (2,))
    transition = transition_type(
        target_running_ns=10,
        downstream_sample=downstream_sample,
        downstream_wait_ns=0,
        candidates=(_sample(wall_model.ThreadIdentity(11, 101), 0, 0, 10, "R", (1,)),),
        evidence="sampled-transition",
    )

    assert (
        latest_transition(
            {downstream: [transition]},
            downstream,
            10,
            include_boundary=False,
        )
        is None
    )
    assert (
        latest_transition(
            {downstream: [transition]},
            downstream,
            10,
            include_boundary=True,
        )
        is transition
    )


# PRF-047: Multi-threaded critical path.
def test_ambiguous_worker_without_main_candidate_keeps_prior_path_uncertain():
    main_thread = wall_model.ThreadIdentity(11, 101)
    worker = wall_model.ThreadIdentity(12, 102)
    other_worker = wall_model.ThreadIdentity(13, 103)
    second_other_worker = wall_model.ThreadIdentity(14, 104)
    worker_sample = _sample(worker, 1, 10, 20, "R", (2,))
    other_worker_sample = _sample(other_worker, 0, 0, 10, "R", (3,))
    second_other_worker_sample = _sample(second_other_worker, 0, 0, 10, "R", (4,))
    terminal_sample = _sample(main_thread, 1, 20, 30, "R", (1,))
    transition_type = wall_critical_path._Transition  # pyright: ignore[reportPrivateUsage]
    phases_and_handoffs = wall_critical_path._phases_and_handoffs  # pyright: ignore[reportPrivateUsage]
    profile = typing.cast(
        "schema.RawProfile",
        typing.cast(
            "object",
            types.SimpleNamespace(
                process_id=main_thread.os_thread_id,
                lifecycle={
                    "python_observed_target_running_ns": 0,
                    "exited_target_running_ns": 30,
                },
                observations=[{}, {}],
            ),
        ),
    )

    skeleton = phases_and_handoffs(
        profile,
        _samples({}, {main_thread: terminal_sample}),
        {
            worker: [
                transition_type(
                    target_running_ns=10,
                    downstream_sample=worker_sample,
                    downstream_wait_ns=0,
                    candidates=(other_worker_sample, second_other_worker_sample),
                    evidence="sampled-transition",
                )
            ],
            main_thread: [
                transition_type(
                    target_running_ns=20,
                    downstream_sample=terminal_sample,
                    downstream_wait_ns=5,
                    candidates=(worker_sample,),
                    evidence="sampled-transition",
                )
            ],
        },
    )

    assert skeleton.uncertain_segments == [
        wall_critical_path.UncertainSegment(
            interval=wall_model.Interval(0, 10),
            reason="critical path before ambiguous handoff was not resolved",
        )
    ]


# PRF-047: Multi-threaded critical path.
def test_phase_without_an_overlapping_sample_is_uncertain():
    actor = wall_model.ThreadIdentity(11, 101)
    boundary_sample = _sample(actor, 0, 0, 10, "R", (1,))
    phase_type = wall_critical_path._Phase  # pyright: ignore[reportPrivateUsage]
    phase_segments = wall_critical_path._phase_segments  # pyright: ignore[reportPrivateUsage]

    segments = phase_segments(
        phase_type(
            interval=wall_model.Interval(10, 20),
            actor=actor,
            waiter=None,
        ),
        _samples({actor: boundary_sample}),
    )

    assert segments == [
        wall_critical_path.UncertainSegment(
            interval=wall_model.Interval(10, 20),
            reason="critical thread was not observed",
        )
    ]
