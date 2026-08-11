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
        identity=identity,
        observation_index=observation_index,
        interval=wall_model.Interval(start_ns, end_ns),
        pre_stop_state=state,
        wait_channel="futex_wait_queue_me" if state == "S" else "0",
        voluntary_context_switches=observation_index,
        nonvoluntary_context_switches=0,
        stack=stack,
    )


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
    first_wait = _sample(downstream, 0, 5, 15, "S", (1,))
    second_wait = _sample(downstream, 1, 15, 25, "S", (1,))
    wait_start = wall_critical_path._wait_start  # pyright: ignore[reportPrivateUsage]

    result = wait_start(
        downstream,
        1,
        {
            0: {downstream: first_wait},
            1: {downstream: second_wait},
        },
        _profile_with_observation_times(10, 20),
    )

    assert result == (0, 5)


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
        {
            0: {
                downstream: _sample(downstream, 0, 0, 10, "S", (3,)),
                producer: first_producer_sample,
            },
            1: {
                downstream: _sample(downstream, 1, 10, 20, "S", (3,)),
                producer: latest_producer_sample,
            },
        },
    )

    assert candidates == [latest_producer_sample]


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
        {
            0: {producer: producer_before},
            1: {
                producer: producer_after,
                downstream: downstream_after,
            },
        },
    )

    assert len(transitions) == 1
    transition = transitions[0]
    assert transition.target_running_ns == 10
    assert transition.earlier_observation_index == 0
    assert transition.downstream == downstream
    assert transition.downstream_stack == (2,)
    assert transition.downstream_wait_ns == 0
    assert transition.candidates == (producer,)
    assert transition.candidate_stacks == ((1,),)


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
        {actor: [boundary_sample]},
        {0: {actor: boundary_sample}},
    )

    assert segments == [
        wall_critical_path.UncertainSegment(
            interval=wall_model.Interval(10, 20),
            reason="critical thread was not observed",
        )
    ]
