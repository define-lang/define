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
    worker_count = 7,
};

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

typedef struct {
    alignas(cache_line_size) atomic_uint remaining;
} OperationDependencies;

static_assert(
    sizeof(OperationDependencies) == cache_line_size,
    "concurrently updated Joins must not share a cache line"
);

static const uint8_t predecessor_counts[operation_count] = {
    0, 1, 2, 2, 3, 2, 2, 2, 4, 2, 1, 2, 2, 1, 2, 1, 3, 1,
    1, 4, 1, 3, 1, 3, 1, 1, 5, 5, 5, 1, 5, 1, 4, 4, 4, 15,
};

alignas(cache_line_size) static unsigned char test_particle;
alignas(cache_line_size) static unsigned char carrier_particle;
alignas(cache_line_size) static unsigned char third_particle;
alignas(cache_line_size) static unsigned char worker_second_interface_particle;
alignas(cache_line_size) static unsigned char worker_first_interface_particle;
alignas(cache_line_size) static unsigned char first_particle;
alignas(cache_line_size) static unsigned char second_particle;
alignas(cache_line_size) static unsigned char fifth_particle;
alignas(cache_line_size) static unsigned char fourth_particle;
alignas(cache_line_size) static unsigned char fourth_destructor_marker_particle;
alignas(cache_line_size) static unsigned char second_destructor_marker_particle;
alignas(cache_line_size) static unsigned char fifth_destructor_marker_particle;
alignas(cache_line_size) static unsigned char first_destructor_marker_particle;
alignas(cache_line_size) static OperationDependencies
    operation_dependencies[operation_count] = {
        [operation_worker_create_second_interface] = {.remaining = 2},
        [operation_worker_create_first_interface] = {.remaining = 2},
        [operation_test_move_carrier_to_middle] = {.remaining = 3},
        [operation_middle_create_first] = {.remaining = 2},
        [operation_middle_create_second] = {.remaining = 2},
        [operation_middle_create_fifth] = {.remaining = 2},
        [operation_middle_move_target_to_destroyer] = {.remaining = 4},
        [operation_destroyer_move_second_to_holder_first] = {.remaining = 2},
        [operation_destroyer_create_fourth] = {.remaining = 2},
        [operation_fifth_destructor_move_fifth_to_holder] = {.remaining = 2},
        [operation_first_destructor_move_first_to_holder] = {.remaining = 2},
        [operation_fourth_destructor_move_fourth_to_holder] = {.remaining = 3},
        [operation_fourth_destructor_create_marker] = {.remaining = 4},
        [operation_second_destructor_create_marker] = {.remaining = 3},
        [operation_second_destructor_move_second_to_holder] = {.remaining = 3},
        [operation_destroyer_destroy_fifth] = {.remaining = 5},
        [operation_destroyer_destroy_first] = {.remaining = 5},
        [operation_fifth_destructor_create_marker] = {.remaining = 5},
        [operation_first_destructor_create_marker] = {.remaining = 5},
        [operation_destroyer_destroy_worker_second_interface] = {
            .remaining = 4,
        },
        [operation_destroyer_destroy_worker_first_interface] = {
            .remaining = 4,
        },
        [operation_destroyer_destroy_third] = {.remaining = 4},
        [operation_destroyer_destroy_target] = {.remaining = 15},
    };
alignas(cache_line_size) static _Atomic uint64_t ready_operations;
alignas(cache_line_size) static atomic_bool program_complete;

[[noreturn]] static void fail_thread_operation(
    const char *operation, int error_number
) {
    errno = error_number;
    perror(operation);
    exit(EXIT_FAILURE);
}

static void publish_operation(enum OperationIdentity operation_identity) {
    uint64_t operation_bit = UINT64_C(1)
        << (unsigned int)operation_identity;
    (void)atomic_fetch_or_explicit(
        &ready_operations, operation_bit, memory_order_release
    );
}

static bool claim_operation(
    enum OperationIdentity *claimed_operation_identity
) {
    uint64_t observed = atomic_load_explicit(
        &ready_operations, memory_order_relaxed
    );
    while (observed != 0) {
        unsigned int bit_index = (unsigned int)__builtin_ctzll(observed);
        uint64_t desired = observed & (observed - 1);
        if (atomic_compare_exchange_weak_explicit(
                &ready_operations,
                &observed,
                desired,
                memory_order_acquire,
                memory_order_relaxed
            )) {
            *claimed_operation_identity =
                (enum OperationIdentity)bit_index;
            return true;
        }
    }
    return false;
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

static bool satisfy_operation(enum OperationIdentity operation_identity) {
    if (predecessor_counts[operation_identity] == 1) {
        return true;
    }
    OperationDependencies *dependencies =
        &operation_dependencies[operation_identity];
    unsigned int previous = atomic_fetch_sub_explicit(
        &dependencies->remaining, 1, memory_order_acq_rel
    );
    return previous == 1;
}

static void select_successor(
    enum OperationIdentity successor,
    enum OperationIdentity *direct_successor
) {
    if (!satisfy_operation(successor)) {
        return;
    }
    if (*direct_successor == operation_no_direct_successor) {
        *direct_successor = successor;
    } else {
        publish_operation(successor);
    }
}

static enum OperationIdentity complete_operation(
    enum OperationIdentity operation_identity
) {
    if (operation_identity == operation_destroyer_destroy_target) {
        atomic_store_explicit(&program_complete, true, memory_order_release);
        return operation_no_direct_successor;
    }
    enum OperationIdentity direct_successor = operation_no_direct_successor;
    switch (operation_identity) {
        case operation_test_create_carrier:
            select_successor(
                operation_test_create_third, &direct_successor
            );
            select_successor(
                operation_worker_create_second_interface, &direct_successor
            );
            select_successor(
                operation_worker_create_second_interface, &direct_successor
            );
            select_successor(
                operation_worker_create_first_interface, &direct_successor
            );
            select_successor(
                operation_worker_create_first_interface, &direct_successor
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
            select_successor(
                operation_middle_create_first, &direct_successor
            );
            select_successor(
                operation_middle_create_first, &direct_successor
            );
            select_successor(
                operation_middle_create_second, &direct_successor
            );
            select_successor(
                operation_middle_create_second, &direct_successor
            );
            select_successor(
                operation_middle_create_fifth, &direct_successor
            );
            select_successor(
                operation_middle_create_fifth, &direct_successor
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
            select_successor(
                operation_destroyer_move_second_to_holder_first,
                &direct_successor
            );
            select_successor(
                operation_destroyer_move_second_to_holder_first,
                &direct_successor
            );
            select_successor(
                operation_destroyer_create_fourth, &direct_successor
            );
            select_successor(
                operation_destroyer_create_fourth, &direct_successor
            );
            select_successor(
                operation_fifth_destructor_move_fifth_to_holder,
                &direct_successor
            );
            select_successor(
                operation_fifth_destructor_move_fifth_to_holder,
                &direct_successor
            );
            select_successor(
                operation_first_destructor_move_first_to_holder,
                &direct_successor
            );
            select_successor(
                operation_first_destructor_move_first_to_holder,
                &direct_successor
            );
            select_successor(
                operation_fourth_destructor_move_fourth_to_holder,
                &direct_successor
            );
            select_successor(
                operation_fourth_destructor_move_fourth_to_holder,
                &direct_successor
            );
            select_successor(
                operation_fourth_destructor_create_marker, &direct_successor
            );
            select_successor(
                operation_fourth_destructor_create_marker, &direct_successor
            );
            select_successor(
                operation_fourth_destructor_create_marker, &direct_successor
            );
            select_successor(
                operation_fourth_destructor_create_marker, &direct_successor
            );
            select_successor(
                operation_second_destructor_create_marker, &direct_successor
            );
            select_successor(
                operation_second_destructor_create_marker, &direct_successor
            );
            select_successor(
                operation_second_destructor_move_second_to_holder,
                &direct_successor
            );
            select_successor(
                operation_second_destructor_move_second_to_holder,
                &direct_successor
            );
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
                operation_fifth_destructor_create_marker, &direct_successor
            );
            select_successor(
                operation_first_destructor_create_marker, &direct_successor
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
            select_successor(
                operation_destroyer_destroy_target, &direct_successor
            );
            select_successor(
                operation_destroyer_destroy_target, &direct_successor
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
            select_successor(
                operation_destroyer_destroy_target, &direct_successor
            );
            select_successor(
                operation_destroyer_destroy_target, &direct_successor
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
    return direct_successor;
}

static void *run_operations(void *unused) {
    (void)unused;
    while (!atomic_load_explicit(&program_complete, memory_order_acquire)) {
        enum OperationIdentity operation_identity;
        if (!claim_operation(&operation_identity)) {
            _mm_pause();
            continue;
        }
        do {
            execute_operation(operation_identity);
            operation_identity = complete_operation(operation_identity);
        } while (operation_identity != operation_no_direct_successor);
    }
    return NULL;
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
