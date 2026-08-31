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
    ready_create_and_destroy_local_item = UINT64_C(1) << 0,
};

alignas(cache_line_size) static unsigned char test_particle;
alignas(cache_line_size) static unsigned char other_trigger_particle;
alignas(cache_line_size) static unsigned char other_item_particle;
alignas(cache_line_size) static unsigned char local_item_particle;
alignas(cache_line_size) static _Atomic uint64_t ready_operations;

[[noreturn]] static void fail_thread_operation(
    const char *operation, int error_number
) {
    errno = error_number;
    perror(operation);
    exit(EXIT_FAILURE);
}

static void action_other(void) {
    other_item_particle = 1;
    other_item_particle = 0;
}

static void create_and_destroy_local_item(void) {
    local_item_particle = 1;
    local_item_particle = 0;
}

static void publish_local_item_branch(void) {
    (void)atomic_fetch_or_explicit(
        &ready_operations,
        ready_create_and_destroy_local_item,
        memory_order_release
    );
}

static bool claim_local_item_branch(void) {
    uint64_t observed = atomic_load_explicit(
        &ready_operations, memory_order_acquire
    );
    while ((observed & ready_create_and_destroy_local_item) != 0) {
        uint64_t desired = observed
            & ~(uint64_t)ready_create_and_destroy_local_item;
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

static void *run_local_item_branch(void *unused) {
    (void)unused;
    while (!claim_local_item_branch()) {
        _mm_pause();
    }
    create_and_destroy_local_item();
    return NULL;
}

static void create_trigger_and_run_other_action(void) {
    other_trigger_particle = 1;
    action_other();
    other_trigger_particle = 0;
}

static void action_test(void) {
    publish_local_item_branch();
    create_trigger_and_run_other_action();
}

int main(void) {
    pthread_t local_item_thread;
    int error_number = pthread_create(
        &local_item_thread, NULL, run_local_item_branch, NULL
    );
    if (error_number != 0) {
        fail_thread_operation("pthread_create", error_number);
    }

    test_particle = 1;
    action_test();

    error_number = pthread_join(local_item_thread, NULL);
    if (error_number != 0) {
        fail_thread_operation("pthread_join", error_number);
    }
    return 0;
}
