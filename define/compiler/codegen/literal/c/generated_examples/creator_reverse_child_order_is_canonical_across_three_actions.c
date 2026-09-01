#include <errno.h>
#include <immintrin.h>
#include <pthread.h>
#include <stdalign.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

enum {
    cache_line_size = 64,
    operation_count = 36,
    worker_count = 2,
};

static const uint64_t program_complete_bit = UINT64_C(1) << 63;

enum OperationIdentity {
    operation_test_create_carrier,
    operation_test_create_third,
    operation_worker_create_second_interface,
    operation_worker_create_first_interface,
    operation_test_move_carrier_to_middle,
    operation_middle_create_first,
    operation_middle_create_second,
    operation_middle_create_fifth,
    operation_middle_move_target_to_destroyer,
    operation_destroyer_move_second_to_holder_first,
    operation_destroyer_move_holder_to_second_first,
    operation_destroyer_create_fourth,
    operation_fifth_destructor_move_fifth_to_holder,
    operation_fifth_destructor_move_holder_to_fifth,
    operation_first_destructor_move_first_to_holder,
    operation_first_destructor_move_holder_to_first,
    operation_fourth_destructor_move_fourth_to_holder,
    operation_fourth_destructor_move_holder_to_fourth,
    operation_destroyer_destroy_fourth,
    operation_fourth_destructor_create_marker,
    operation_fourth_destructor_destroy_marker,
    operation_second_destructor_create_marker,
    operation_second_destructor_destroy_marker,
    operation_second_destructor_move_second_to_holder,
    operation_second_destructor_move_holder_to_second,
    operation_destroyer_destroy_second,
    operation_destroyer_destroy_fifth,
    operation_destroyer_destroy_first,
    operation_fifth_destructor_create_marker,
    operation_fifth_destructor_destroy_marker,
    operation_first_destructor_create_marker,
    operation_first_destructor_destroy_marker,
    operation_destroyer_destroy_worker_second_interface,
    operation_destroyer_destroy_worker_first_interface,
    operation_destroyer_destroy_third,
    operation_destroyer_destroy_target,
    operation_no_direct_successor,
};

static_assert(
    (int)operation_no_direct_successor == operation_count,
    "every Operation identity must have generated topology"
);
static_assert(
    operation_count <= 63,
    "operation identities must not overlap the completion bit"
);

static unsigned char test_particle;
static unsigned char carrier_particle;
static unsigned char third_particle;
static unsigned char worker_second_interface_particle;
static unsigned char worker_first_interface_particle;
static unsigned char first_particle;
static unsigned char second_particle;
static unsigned char fifth_particle;
static unsigned char fourth_particle;
static unsigned char fourth_destructor_marker_particle;
static unsigned char second_destructor_marker_particle;
static unsigned char fifth_destructor_marker_particle;
static unsigned char first_destructor_marker_particle;

typedef struct {
    atomic_uint test_move_carrier_to_middle;
    atomic_uint middle_move_target_to_destroyer;
} SequentialJoins;

alignas(cache_line_size) static SequentialJoins sequential_joins = {
    .test_move_carrier_to_middle = 3,
    .middle_move_target_to_destroyer = 4,
};
alignas(cache_line_size) static atomic_uint
    join_fourth_destructor_move_fourth_to_holder = 3;
alignas(cache_line_size) static atomic_uint
    join_second_destructor_create_marker = 3;
alignas(cache_line_size) static atomic_uint
    join_second_destructor_move_second_to_holder = 3;
alignas(cache_line_size) static atomic_uint join_destroyer_destroy_fifth = 5;
alignas(cache_line_size) static atomic_uint join_destroyer_destroy_first = 5;
alignas(cache_line_size) static atomic_uint
    join_fifth_destructor_create_marker = 5;
alignas(cache_line_size) static atomic_uint
    join_first_destructor_create_marker = 5;
alignas(cache_line_size) static atomic_uint
    join_destroyer_destroy_worker_second_interface = 4;
alignas(cache_line_size) static atomic_uint
    join_destroyer_destroy_worker_first_interface = 4;
alignas(cache_line_size) static atomic_uint join_destroyer_destroy_third = 4;
alignas(cache_line_size) static atomic_uint join_destroyer_destroy_target = 15;
alignas(cache_line_size) static _Atomic uint64_t ready_operations;

[[noreturn]] static void fail_thread_operation(
    const char *operation, int error_number
) {
    errno = error_number;
    perror(operation);
    _Exit(EXIT_FAILURE);
}

static void publish_operation(enum OperationIdentity operation_identity) {
    uint64_t operation_bit = UINT64_C(1)
        << (unsigned int)operation_identity;
    (void)atomic_fetch_or_explicit(
        &ready_operations, operation_bit, memory_order_acq_rel
    );
}

typedef struct {
    enum OperationIdentity operation_identity;
    uint64_t published_operations;
} NewlySatisfiedOperations;

enum ClaimResult {
    claim_result_none,
    claim_result_operation,
    claim_result_program_complete,
};

static enum ClaimResult claim_operation(
    enum OperationIdentity *claimed_operation_identity
) {
    uint64_t observed = atomic_load_explicit(
        &ready_operations, memory_order_acquire
    );
    for (;;) {
        if ((observed & program_complete_bit) != 0) {
            return claim_result_program_complete;
        }
        if (observed == 0) {
            return claim_result_none;
        }
        unsigned int bit_index = (unsigned int)__builtin_ctzll(observed);
        uint64_t desired = observed & ~(UINT64_C(1) << bit_index);
        if (atomic_compare_exchange_weak_explicit(
                &ready_operations,
                &observed,
                desired,
                memory_order_acquire,
                memory_order_relaxed
            )) {
            *claimed_operation_identity =
                (enum OperationIdentity)bit_index;
            return claim_result_operation;
        }
    }
}

static void execute_operation(enum OperationIdentity operation_identity) {
    switch (operation_identity) {
        case operation_test_create_carrier:
            carrier_particle = 1;
            break;
        case operation_test_create_third:
            third_particle = 1;
            break;
        case operation_worker_create_second_interface:
            worker_second_interface_particle = 1;
            break;
        case operation_worker_create_first_interface:
            worker_first_interface_particle = 1;
            break;
        case operation_middle_create_first:
            first_particle = 1;
            break;
        case operation_middle_create_second:
            second_particle = 1;
            break;
        case operation_middle_create_fifth:
            fifth_particle = 1;
            break;
        case operation_destroyer_create_fourth:
            fourth_particle = 1;
            break;
        case operation_fourth_destructor_create_marker:
            fourth_destructor_marker_particle = 1;
            break;
        case operation_second_destructor_create_marker:
            second_destructor_marker_particle = 1;
            break;
        case operation_fifth_destructor_create_marker:
            fifth_destructor_marker_particle = 1;
            break;
        case operation_first_destructor_create_marker:
            first_destructor_marker_particle = 1;
            break;
        case operation_destroyer_destroy_fourth:
            fourth_particle = 0;
            break;
        case operation_fourth_destructor_destroy_marker:
            fourth_destructor_marker_particle = 0;
            break;
        case operation_second_destructor_destroy_marker:
            second_destructor_marker_particle = 0;
            break;
        case operation_destroyer_destroy_second:
            second_particle = 0;
            break;
        case operation_destroyer_destroy_fifth:
            fifth_particle = 0;
            break;
        case operation_destroyer_destroy_first:
            first_particle = 0;
            break;
        case operation_fifth_destructor_destroy_marker:
            fifth_destructor_marker_particle = 0;
            break;
        case operation_first_destructor_destroy_marker:
            first_destructor_marker_particle = 0;
            break;
        case operation_destroyer_destroy_worker_second_interface:
            worker_second_interface_particle = 0;
            break;
        case operation_destroyer_destroy_worker_first_interface:
            worker_first_interface_particle = 0;
            break;
        case operation_destroyer_destroy_third:
            third_particle = 0;
            break;
        case operation_destroyer_destroy_target:
            carrier_particle = 0;
            break;
        case operation_test_move_carrier_to_middle:
        case operation_middle_move_target_to_destroyer:
        case operation_destroyer_move_second_to_holder_first:
        case operation_destroyer_move_holder_to_second_first:
        case operation_fifth_destructor_move_fifth_to_holder:
        case operation_fifth_destructor_move_holder_to_fifth:
        case operation_first_destructor_move_first_to_holder:
        case operation_first_destructor_move_holder_to_first:
        case operation_fourth_destructor_move_fourth_to_holder:
        case operation_fourth_destructor_move_holder_to_fourth:
        case operation_second_destructor_move_second_to_holder:
        case operation_second_destructor_move_holder_to_second:
            break;
        case operation_no_direct_successor:
            __builtin_unreachable();
    }
}

static bool satisfy_operation(
    enum OperationIdentity operation_identity, unsigned int arrival_count
) {
    atomic_uint *remaining;
    switch (operation_identity) {
        case operation_test_move_carrier_to_middle:
            remaining = &sequential_joins.test_move_carrier_to_middle;
            break;
        case operation_middle_move_target_to_destroyer:
            remaining = &sequential_joins.middle_move_target_to_destroyer;
            break;
        case operation_fourth_destructor_move_fourth_to_holder:
            remaining = &join_fourth_destructor_move_fourth_to_holder;
            break;
        case operation_second_destructor_create_marker:
            remaining = &join_second_destructor_create_marker;
            break;
        case operation_second_destructor_move_second_to_holder:
            remaining = &join_second_destructor_move_second_to_holder;
            break;
        case operation_destroyer_destroy_fifth:
            remaining = &join_destroyer_destroy_fifth;
            break;
        case operation_destroyer_destroy_first:
            remaining = &join_destroyer_destroy_first;
            break;
        case operation_fifth_destructor_create_marker:
            remaining = &join_fifth_destructor_create_marker;
            break;
        case operation_first_destructor_create_marker:
            remaining = &join_first_destructor_create_marker;
            break;
        case operation_destroyer_destroy_worker_second_interface:
            remaining = &join_destroyer_destroy_worker_second_interface;
            break;
        case operation_destroyer_destroy_worker_first_interface:
            remaining = &join_destroyer_destroy_worker_first_interface;
            break;
        case operation_destroyer_destroy_third:
            remaining = &join_destroyer_destroy_third;
            break;
        case operation_destroyer_destroy_target:
            remaining = &join_destroyer_destroy_target;
            break;
        default:
            return true;
    }
    unsigned int previous = atomic_fetch_sub_explicit(
        remaining, arrival_count, memory_order_acq_rel
    );
    return previous == arrival_count;
}

static void select_successor_arrivals(
    enum OperationIdentity successor,
    unsigned int arrival_count,
    NewlySatisfiedOperations *newly_satisfied
) {
    if (!satisfy_operation(successor, arrival_count)) {
        return;
    }
    if (newly_satisfied->operation_identity == operation_no_direct_successor) {
        newly_satisfied->operation_identity = successor;
    } else {
        newly_satisfied->published_operations |= UINT64_C(1)
            << (unsigned int)successor;
    }
}

static void select_successor(
    enum OperationIdentity successor,
    NewlySatisfiedOperations *newly_satisfied
) {
    select_successor_arrivals(successor, 1, newly_satisfied);
}

static enum OperationIdentity complete_operation(
    enum OperationIdentity operation_identity
) {
    if (operation_identity == operation_destroyer_destroy_target) {
        atomic_store_explicit(
            &ready_operations, program_complete_bit, memory_order_release
        );
        return operation_no_direct_successor;
    }
    NewlySatisfiedOperations direct_successor = {
        .operation_identity = operation_no_direct_successor,
    };
    switch (operation_identity) {
        case operation_test_create_carrier:
            select_successor(
                operation_test_create_third, &direct_successor
            );
            select_successor_arrivals(
                operation_worker_create_second_interface,
                2,
                &direct_successor
            );
            select_successor_arrivals(
                operation_worker_create_first_interface,
                2,
                &direct_successor
            );
            break;
        case operation_test_create_third:
        case operation_worker_create_second_interface:
        case operation_worker_create_first_interface:
            select_successor(
                operation_test_move_carrier_to_middle, &direct_successor
            );
            break;
        case operation_test_move_carrier_to_middle:
            select_successor_arrivals(
                operation_middle_create_first, 2, &direct_successor
            );
            select_successor_arrivals(
                operation_middle_create_second, 2, &direct_successor
            );
            select_successor_arrivals(
                operation_middle_create_fifth, 2, &direct_successor
            );
            select_successor(
                operation_middle_move_target_to_destroyer, &direct_successor
            );
            break;
        case operation_middle_create_first:
        case operation_middle_create_second:
        case operation_middle_create_fifth:
            select_successor(
                operation_middle_move_target_to_destroyer, &direct_successor
            );
            break;
        case operation_middle_move_target_to_destroyer:
            select_successor_arrivals(
                operation_destroyer_move_second_to_holder_first,
                2,
                &direct_successor
            );
            select_successor_arrivals(
                operation_destroyer_create_fourth, 2, &direct_successor
            );
            select_successor_arrivals(
                operation_fifth_destructor_move_fifth_to_holder,
                2,
                &direct_successor
            );
            select_successor_arrivals(
                operation_first_destructor_move_first_to_holder,
                2,
                &direct_successor
            );
            select_successor_arrivals(
                operation_fourth_destructor_move_fourth_to_holder,
                2,
                &direct_successor
            );
            select_successor_arrivals(
                operation_fourth_destructor_create_marker,
                4,
                &direct_successor
            );
            select_successor_arrivals(
                operation_second_destructor_create_marker,
                2,
                &direct_successor
            );
            select_successor_arrivals(
                operation_second_destructor_move_second_to_holder,
                2,
                &direct_successor
            );
            select_successor(
                operation_destroyer_destroy_fifth, &direct_successor
            );
            select_successor(
                operation_destroyer_destroy_first, &direct_successor
            );
            select_successor_arrivals(
                operation_fifth_destructor_create_marker,
                2,
                &direct_successor
            );
            select_successor_arrivals(
                operation_first_destructor_create_marker,
                2,
                &direct_successor
            );
            select_successor(
                operation_destroyer_destroy_worker_second_interface,
                &direct_successor
            );
            select_successor(
                operation_destroyer_destroy_worker_first_interface,
                &direct_successor
            );
            select_successor(
                operation_destroyer_destroy_third, &direct_successor
            );
            select_successor_arrivals(
                operation_destroyer_destroy_target, 2, &direct_successor
            );
            break;
        case operation_destroyer_move_second_to_holder_first:
            select_successor(
                operation_destroyer_move_holder_to_second_first,
                &direct_successor
            );
            break;
        case operation_destroyer_move_holder_to_second_first:
            select_successor(
                operation_second_destructor_move_second_to_holder,
                &direct_successor
            );
            break;
        case operation_destroyer_create_fourth:
            select_successor(
                operation_fourth_destructor_move_fourth_to_holder,
                &direct_successor
            );
            break;
        case operation_fifth_destructor_move_fifth_to_holder:
            select_successor(
                operation_fifth_destructor_move_holder_to_fifth,
                &direct_successor
            );
            break;
        case operation_fifth_destructor_move_holder_to_fifth:
            select_successor(
                operation_destroyer_destroy_fifth, &direct_successor
            );
            break;
        case operation_first_destructor_move_first_to_holder:
            select_successor(
                operation_first_destructor_move_holder_to_first,
                &direct_successor
            );
            break;
        case operation_first_destructor_move_holder_to_first:
            select_successor(
                operation_destroyer_destroy_first, &direct_successor
            );
            break;
        case operation_fourth_destructor_move_fourth_to_holder:
            select_successor(
                operation_fourth_destructor_move_holder_to_fourth,
                &direct_successor
            );
            break;
        case operation_fourth_destructor_move_holder_to_fourth:
            select_successor(
                operation_destroyer_destroy_fourth, &direct_successor
            );
            break;
        case operation_destroyer_destroy_fourth:
        case operation_second_destructor_destroy_marker:
        case operation_destroyer_destroy_second:
            select_successor(
                operation_destroyer_destroy_fifth, &direct_successor
            );
            select_successor(
                operation_destroyer_destroy_first, &direct_successor
            );
            select_successor(
                operation_fifth_destructor_create_marker, &direct_successor
            );
            select_successor(
                operation_first_destructor_create_marker, &direct_successor
            );
            select_successor(
                operation_destroyer_destroy_worker_second_interface,
                &direct_successor
            );
            select_successor(
                operation_destroyer_destroy_worker_first_interface,
                &direct_successor
            );
            select_successor(
                operation_destroyer_destroy_third, &direct_successor
            );
            select_successor_arrivals(
                operation_destroyer_destroy_target, 2, &direct_successor
            );
            break;
        case operation_fourth_destructor_create_marker:
            select_successor(
                operation_fourth_destructor_destroy_marker, &direct_successor
            );
            break;
        case operation_fourth_destructor_destroy_marker:
            select_successor(
                operation_second_destructor_create_marker, &direct_successor
            );
            break;
        case operation_second_destructor_create_marker:
            select_successor(
                operation_second_destructor_destroy_marker, &direct_successor
            );
            break;
        case operation_second_destructor_move_second_to_holder:
            select_successor(
                operation_second_destructor_move_holder_to_second,
                &direct_successor
            );
            break;
        case operation_second_destructor_move_holder_to_second:
            select_successor(
                operation_destroyer_destroy_second, &direct_successor
            );
            break;
        case operation_destroyer_destroy_fifth:
        case operation_destroyer_destroy_first:
        case operation_fifth_destructor_destroy_marker:
        case operation_first_destructor_destroy_marker:
        case operation_destroyer_destroy_worker_second_interface:
        case operation_destroyer_destroy_worker_first_interface:
        case operation_destroyer_destroy_third:
            select_successor(
                operation_destroyer_destroy_target, &direct_successor
            );
            break;
        case operation_fifth_destructor_create_marker:
            select_successor(
                operation_fifth_destructor_destroy_marker, &direct_successor
            );
            break;
        case operation_first_destructor_create_marker:
            select_successor(
                operation_first_destructor_destroy_marker, &direct_successor
            );
            break;
        case operation_destroyer_destroy_target:
        case operation_no_direct_successor:
            __builtin_unreachable();
    }
    if (direct_successor.published_operations != 0) {
        (void)atomic_fetch_or_explicit(
            &ready_operations,
            direct_successor.published_operations,
            memory_order_acq_rel
        );
    }
    return direct_successor.operation_identity;
}

static void *run_operations(void *unused) {
    (void)unused;
    for (;;) {
        enum OperationIdentity operation_identity;
        enum ClaimResult claim_result = claim_operation(&operation_identity);
        if (claim_result == claim_result_program_complete) {
            return NULL;
        }
        if (claim_result == claim_result_none) {
            _mm_pause();
            continue;
        }
        do {
            execute_operation(operation_identity);
            operation_identity = complete_operation(operation_identity);
        } while (operation_identity != operation_no_direct_successor);
    }
}

int main(void) {
    test_particle = 1;
    publish_operation(operation_test_create_carrier);

    pthread_t threads[worker_count - 1];
    for (size_t worker_index = 0;
         worker_index < worker_count - 1;
         ++worker_index) {
        int error_number = pthread_create(
            &threads[worker_index], NULL, run_operations, NULL
        );
        if (error_number != 0) {
            fail_thread_operation("pthread_create", error_number);
        }
    }
    (void)run_operations(NULL);
    for (size_t worker_index = 0;
         worker_index < worker_count - 1;
         ++worker_index) {
        int error_number = pthread_join(threads[worker_index], NULL);
        if (error_number != 0) {
            fail_thread_operation("pthread_join", error_number);
        }
    }
    return 0;
}
