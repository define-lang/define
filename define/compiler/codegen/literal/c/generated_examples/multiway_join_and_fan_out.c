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
};

enum ReadyOperation {
    ready_create_and_destroy_box_position_a = UINT64_C(1) << 0,
};

alignas(cache_line_size) static unsigned char test_particle;
alignas(cache_line_size) static unsigned char box_particle;
alignas(cache_line_size) static unsigned char box_position_a_particle;
alignas(cache_line_size) static unsigned char box_position_b_particle;
alignas(cache_line_size) static _Atomic uint64_t ready_operations;
alignas(cache_line_size) static atomic_uint destroy_box_join = 2;

[[noreturn]] static void fail_thread_operation(
    const char *operation, int error_number
) {
    errno = error_number;
    perror(operation);
    exit(EXIT_FAILURE);
}

static void destroy_box(void) {
    box_particle = 0;
}

static void arrive_at_destroy_box_join(void) {
    unsigned int previous = atomic_fetch_sub_explicit(
        &destroy_box_join, 1, memory_order_acq_rel
    );
    if (previous == 1) {
        destroy_box();
    }
}

static void create_and_destroy_box_position_a(void) {
    box_position_a_particle = 1;
    box_position_a_particle = 0;
    arrive_at_destroy_box_join();
}

static void create_and_destroy_box_position_b(void) {
    box_position_b_particle = 1;
    box_position_b_particle = 0;
    arrive_at_destroy_box_join();
}

static void publish_box_position_a(void) {
    (void)atomic_fetch_or_explicit(
        &ready_operations,
        ready_create_and_destroy_box_position_a,
        memory_order_release
    );
}

static bool claim_box_position_a(void) {
    uint64_t observed = atomic_load_explicit(
        &ready_operations, memory_order_acquire
    );
    while ((observed & ready_create_and_destroy_box_position_a) != 0) {
        uint64_t desired = observed
            & ~(uint64_t)ready_create_and_destroy_box_position_a;
        if (atomic_compare_exchange_weak_explicit(
                &ready_operations,
                &observed,
                desired,
                memory_order_acquire,
                memory_order_relaxed
            )) {
            return true;
        }
    }
    return false;
}

static void *run_published_branch(void *unused) {
    (void)unused;
    while (!claim_box_position_a()) {
        _mm_pause();
    }
    create_and_destroy_box_position_a();
    return NULL;
}

static void action_test(void) {
    box_particle = 1;
    publish_box_position_a();
    create_and_destroy_box_position_b();
}

int main(void) {
    pthread_t published_branch_thread;
    int error_number = pthread_create(
        &published_branch_thread, NULL, run_published_branch, NULL
    );
    if (error_number != 0) {
        fail_thread_operation("pthread_create", error_number);
    }

    test_particle = 1;
    action_test();

    error_number = pthread_join(published_branch_thread, NULL);
    if (error_number != 0) {
        fail_thread_operation("pthread_join", error_number);
    }
    return 0;
}
