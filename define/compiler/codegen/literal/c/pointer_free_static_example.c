#include <errno.h>
#if defined(__i386__) || defined(__x86_64__)
#include <immintrin.h>
#endif
#include <inttypes.h>
#include <limits.h>
#include <pthread.h>
#include <stdalign.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#define DEFINE_LITERAL_STRATEGY_DIRECT 1
#define DEFINE_LITERAL_STRATEGY_DIRECT_RANGES 2
#define DEFINE_LITERAL_STRATEGY_CLAIMABLE 3

/*
 * A generator can emit these values before the shared implementation or pass
 * equivalent -D options. Every conditional below is resolved by the C compiler.
 */
#if !defined(DEFINE_LITERAL_STRATEGY)
#define DEFINE_LITERAL_STRATEGY DEFINE_LITERAL_STRATEGY_DIRECT
#endif

#if !defined(DEFINE_LITERAL_EXECUTION_COUNT)
#define DEFINE_LITERAL_EXECUTION_COUNT 1024
#endif

#if !defined(DEFINE_LITERAL_WORKER_COUNT)
#define DEFINE_LITERAL_WORKER_COUNT 8
#endif

#if !defined(DEFINE_LITERAL_INITIAL_CLAIM_LIMIT)
#define DEFINE_LITERAL_INITIAL_CLAIM_LIMIT 1
#endif

#if !defined(DEFINE_LITERAL_DYNAMIC_CLAIM_LIMIT)
#define DEFINE_LITERAL_DYNAMIC_CLAIM_LIMIT 1
#endif

#if !defined(DEFINE_LITERAL_WORK_ROUNDS)
#define DEFINE_LITERAL_WORK_ROUNDS 64
#endif

#if !defined(DEFINE_LITERAL_CACHE_LINE_SIZE)
#define DEFINE_LITERAL_CACHE_LINE_SIZE 64
#endif

#if !defined(DEFINE_LITERAL_PREPARE_WORKER)
#define DEFINE_LITERAL_PREPARE_WORKER(worker_index) ((void)(worker_index))
#endif

#if DEFINE_LITERAL_STRATEGY < DEFINE_LITERAL_STRATEGY_DIRECT \
    || DEFINE_LITERAL_STRATEGY > DEFINE_LITERAL_STRATEGY_CLAIMABLE
#error "invalid literal execution strategy"
#endif

#if DEFINE_LITERAL_EXECUTION_COUNT < 1
#error "the generated program requires at least one Action Execution"
#endif

#if DEFINE_LITERAL_WORKER_COUNT < 1
#error "the generated program requires at least one worker"
#endif

#if DEFINE_LITERAL_INITIAL_CLAIM_LIMIT < 1 \
    || DEFINE_LITERAL_INITIAL_CLAIM_LIMIT > 64
#error "the initial claim limit must be between 1 and 64"
#endif

#if DEFINE_LITERAL_DYNAMIC_CLAIM_LIMIT < 1 \
    || DEFINE_LITERAL_DYNAMIC_CLAIM_LIMIT > 64
#error "the dynamic claim limit must be between 1 and 64"
#endif

#if DEFINE_LITERAL_CACHE_LINE_SIZE < 1
#error "the generated cache-line size must be positive"
#endif

#if DEFINE_LITERAL_WORK_ROUNDS < 0 || DEFINE_LITERAL_WORK_ROUNDS > UINT_MAX
#error "the operation workload does not fit unsigned int"
#endif

#if DEFINE_LITERAL_STRATEGY == DEFINE_LITERAL_STRATEGY_DIRECT_RANGES \
    && DEFINE_LITERAL_WORKER_COUNT > DEFINE_LITERAL_EXECUTION_COUNT
#error "direct ranges require at least one Action Execution per worker"
#endif

static_assert(
    (DEFINE_LITERAL_CACHE_LINE_SIZE
     & (DEFINE_LITERAL_CACHE_LINE_SIZE - 1))
        == 0,
    "the generated cache-line size must be a power of two"
);

typedef struct {
#if DEFINE_LITERAL_STRATEGY == DEFINE_LITERAL_STRATEGY_CLAIMABLE
    alignas(DEFINE_LITERAL_CACHE_LINE_SIZE) uint64_t box;
    alignas(DEFINE_LITERAL_CACHE_LINE_SIZE) uint64_t child_a;
    alignas(DEFINE_LITERAL_CACHE_LINE_SIZE) uint64_t child_b;
    alignas(DEFINE_LITERAL_CACHE_LINE_SIZE) atomic_uint join_remaining;
#else
    uint64_t box;
    uint64_t child_a;
    uint64_t child_b;
#endif
    uint64_t result;
} LiteralActionExecution;

#if DEFINE_LITERAL_STRATEGY == DEFINE_LITERAL_STRATEGY_CLAIMABLE
static_assert(
    sizeof(LiteralActionExecution) % DEFINE_LITERAL_CACHE_LINE_SIZE == 0,
    "concurrent Action Executions must not share a cache line"
);
#endif

alignas(DEFINE_LITERAL_CACHE_LINE_SIZE) static LiteralActionExecution
    action_executions[DEFINE_LITERAL_EXECUTION_COUNT];

#if DEFINE_LITERAL_STRATEGY == DEFINE_LITERAL_STRATEGY_DIRECT_RANGES
typedef struct {
    size_t index;
} LiteralWorker;

static LiteralWorker workers[DEFINE_LITERAL_WORKER_COUNT];
#elif DEFINE_LITERAL_STRATEGY == DEFINE_LITERAL_STRATEGY_CLAIMABLE
enum {
    ready_word_count = (DEFINE_LITERAL_EXECUTION_COUNT + 63) / 64,
};

typedef struct {
    size_t index;
    size_t ready_word_cursor;
    size_t claimed_word_index;
    uint64_t claimed_bits;
} LiteralWorker;

static LiteralWorker workers[DEFINE_LITERAL_WORKER_COUNT];
alignas(DEFINE_LITERAL_CACHE_LINE_SIZE) static atomic_size_t
    next_initial_execution;
alignas(DEFINE_LITERAL_CACHE_LINE_SIZE) static atomic_size_t
    remaining_execution_count;
alignas(DEFINE_LITERAL_CACHE_LINE_SIZE) static _Atomic uint64_t
    ready_child_b[ready_word_count];
#endif

#if DEFINE_LITERAL_STRATEGY != DEFINE_LITERAL_STRATEGY_DIRECT
[[noreturn]] static void fail_errno(const char *operation, int error_number) {
    errno = error_number;
    perror(operation);
    exit(EXIT_FAILURE);
}
#endif

#if DEFINE_LITERAL_STRATEGY == DEFINE_LITERAL_STRATEGY_CLAIMABLE
[[noreturn]] static void fail_message(const char *message) {
    fputs(message, stderr);
    fputc('\n', stderr);
    exit(EXIT_FAILURE);
}

static void processor_relax(void) {
#if defined(__i386__) || defined(__x86_64__)
    _mm_pause();
#elif defined(__aarch64__)
    __asm__ volatile("yield");
#else
    atomic_signal_fence(memory_order_seq_cst);
#endif
}
#endif

static uint64_t perform_operation_work(uint64_t value, uint64_t salt) {
    value ^= salt;
#if DEFINE_LITERAL_WORK_ROUNDS > 0
    for (unsigned int round = 0; round < DEFINE_LITERAL_WORK_ROUNDS; ++round) {
        value ^= value << 13;
        value ^= value >> 7;
        value ^= value << 17;
    }
#endif
    return value;
}

static uint64_t action_execution_seed(size_t execution_index) {
    return UINT64_C(0x9e3779b97f4a7c15) + (uint64_t)execution_index;
}

static void create_box(size_t execution_index) {
    LiteralActionExecution *execution = &action_executions[execution_index];
    execution->box = perform_operation_work(
        action_execution_seed(execution_index),
        UINT64_C(0x243f6a8885a308d3)
    );
}

static void create_and_destroy_child_a(size_t execution_index) {
    LiteralActionExecution *execution = &action_executions[execution_index];
    execution->child_a = perform_operation_work(
        action_execution_seed(execution_index),
        UINT64_C(0x452821e638d01377)
    );
    execution->child_a = perform_operation_work(
        execution->child_a, UINT64_C(0xbe5466cf34e90c6c)
    );
}

static void create_and_destroy_child_b(size_t execution_index) {
    LiteralActionExecution *execution = &action_executions[execution_index];
    execution->child_b = perform_operation_work(
        action_execution_seed(execution_index),
        UINT64_C(0xc0ac29b7c97c50dd)
    );
    execution->child_b = perform_operation_work(
        execution->child_b, UINT64_C(0x3f84d5b5b5470917)
    );
}

static void destroy_box(size_t execution_index) {
    LiteralActionExecution *execution = &action_executions[execution_index];
    execution->box = perform_operation_work(
        execution->box ^ execution->child_a
            ^ (execution->child_b << 1),
        UINT64_C(0x082efa98ec4e6c89)
    );
    execution->result = execution->box;
}

#if DEFINE_LITERAL_STRATEGY != DEFINE_LITERAL_STRATEGY_CLAIMABLE
static void execute_complete_graph(size_t execution_index) {
    create_box(execution_index);
    create_and_destroy_child_a(execution_index);
    create_and_destroy_child_b(execution_index);
    destroy_box(execution_index);
}
#else
static uint64_t select_low_bits(uint64_t bits) {
    uint64_t selected = 0;
    for (size_t count = 0;
         count < DEFINE_LITERAL_DYNAMIC_CLAIM_LIMIT && bits != 0;
         ++count) {
        uint64_t bit = bits & (~bits + 1);
        selected |= bit;
        bits ^= bit;
    }
    return selected;
}

static void publish_child_b(size_t execution_index) {
    size_t word_index = execution_index / 64;
    uint64_t bit = UINT64_C(1) << (execution_index % 64);
    (void)atomic_fetch_or_explicit(
        &ready_child_b[word_index], bit, memory_order_acq_rel
    );
}

static bool claim_child_b(
    LiteralWorker *worker, size_t *claimed_execution_index
) {
    if (worker->claimed_bits != 0) {
        unsigned int bit_index = (unsigned int)__builtin_ctzll(
            worker->claimed_bits
        );
        worker->claimed_bits &= worker->claimed_bits - 1;
        *claimed_execution_index = worker->claimed_word_index * 64 + bit_index;
        return true;
    }

    size_t cursor = worker->ready_word_cursor;
    for (size_t offset = 0; offset < ready_word_count; ++offset) {
        uint64_t observed = atomic_load_explicit(
            &ready_child_b[cursor], memory_order_relaxed
        );
        while (observed != 0) {
            uint64_t claimed = select_low_bits(observed);
            uint64_t desired = observed & ~claimed;
            if (!atomic_compare_exchange_weak_explicit(
                    &ready_child_b[cursor],
                    &observed,
                    desired,
                    memory_order_acquire,
                    memory_order_relaxed
                )) {
                continue;
            }
            unsigned int bit_index = (unsigned int)__builtin_ctzll(claimed);
            worker->claimed_bits = claimed & (claimed - 1);
            worker->claimed_word_index = cursor;
            *claimed_execution_index = cursor * 64 + bit_index;
            ++cursor;
            if (cursor == ready_word_count) {
                cursor = 0;
            }
            worker->ready_word_cursor = cursor;
            return true;
        }
        ++cursor;
        if (cursor == ready_word_count) {
            cursor = 0;
        }
    }
    worker->ready_word_cursor = cursor;
    return false;
}

static void finish_branch(size_t execution_index) {
    LiteralActionExecution *execution = &action_executions[execution_index];
    if (atomic_fetch_sub_explicit(
            &execution->join_remaining, 1, memory_order_acq_rel
        ) == 1) {
        destroy_box(execution_index);
        (void)atomic_fetch_sub_explicit(
            &remaining_execution_count, 1, memory_order_acq_rel
        );
    }
}

static void execute_initial_branch(size_t execution_index) {
    create_box(execution_index);
    publish_child_b(execution_index);
    create_and_destroy_child_a(execution_index);
    finish_branch(execution_index);
}

static void execute_published_branch(size_t execution_index) {
    create_and_destroy_child_b(execution_index);
    finish_branch(execution_index);
}
#endif

static void initialize_program(void) {
#if DEFINE_LITERAL_STRATEGY == DEFINE_LITERAL_STRATEGY_CLAIMABLE
    for (size_t execution_index = 0;
         execution_index < DEFINE_LITERAL_EXECUTION_COUNT;
         ++execution_index) {
        LiteralActionExecution *execution =
            &action_executions[execution_index];
        atomic_store_explicit(
            &execution->join_remaining, 2, memory_order_relaxed
        );
    }
#endif

#if DEFINE_LITERAL_STRATEGY == DEFINE_LITERAL_STRATEGY_DIRECT_RANGES
    for (size_t worker_index = 0;
         worker_index < DEFINE_LITERAL_WORKER_COUNT;
         ++worker_index) {
        workers[worker_index].index = worker_index;
    }
#elif DEFINE_LITERAL_STRATEGY == DEFINE_LITERAL_STRATEGY_CLAIMABLE
    atomic_store_explicit(&next_initial_execution, 0, memory_order_relaxed);
    atomic_store_explicit(
        &remaining_execution_count,
        DEFINE_LITERAL_EXECUTION_COUNT,
        memory_order_relaxed
    );
    for (size_t word_index = 0; word_index < ready_word_count; ++word_index) {
        atomic_store_explicit(
            &ready_child_b[word_index], 0, memory_order_relaxed
        );
    }
    for (size_t worker_index = 0;
         worker_index < DEFINE_LITERAL_WORKER_COUNT;
         ++worker_index) {
        workers[worker_index] = (LiteralWorker){
            .index = worker_index,
            .ready_word_cursor = worker_index % ready_word_count,
        };
    }
    if (!atomic_is_lock_free(&next_initial_execution)
        || !atomic_is_lock_free(&remaining_execution_count)
        || !atomic_is_lock_free(&ready_child_b[0])
        || !atomic_is_lock_free(&action_executions[0].join_remaining)) {
        fail_message("the generated atomic representation is not lock-free");
    }
#endif
}

#if DEFINE_LITERAL_STRATEGY == DEFINE_LITERAL_STRATEGY_DIRECT_RANGES
static void *run_direct_range(void *opaque_worker) {
    const LiteralWorker *worker = opaque_worker;
    DEFINE_LITERAL_PREPARE_WORKER(worker->index);
    size_t first_execution = DEFINE_LITERAL_EXECUTION_COUNT * worker->index
        / DEFINE_LITERAL_WORKER_COUNT;
    size_t execution_limit = DEFINE_LITERAL_EXECUTION_COUNT
        * (worker->index + 1) / DEFINE_LITERAL_WORKER_COUNT;
    for (size_t execution_index = first_execution;
         execution_index < execution_limit;
         ++execution_index) {
        execute_complete_graph(execution_index);
    }
    return NULL;
}
#elif DEFINE_LITERAL_STRATEGY == DEFINE_LITERAL_STRATEGY_CLAIMABLE
static void execute_initial_claims(void) {
    for (;;) {
        size_t first_execution = atomic_fetch_add_explicit(
            &next_initial_execution,
            DEFINE_LITERAL_INITIAL_CLAIM_LIMIT,
            memory_order_relaxed
        );
        if (first_execution >= DEFINE_LITERAL_EXECUTION_COUNT) {
            return;
        }
        size_t execution_limit = first_execution
            + DEFINE_LITERAL_INITIAL_CLAIM_LIMIT;
        if (execution_limit > DEFINE_LITERAL_EXECUTION_COUNT) {
            execution_limit = DEFINE_LITERAL_EXECUTION_COUNT;
        }
        for (size_t execution_index = first_execution;
             execution_index < execution_limit;
             ++execution_index) {
            execute_initial_branch(execution_index);
        }
    }
}

static void *run_claimable(void *opaque_worker) {
    LiteralWorker *worker = opaque_worker;
    DEFINE_LITERAL_PREPARE_WORKER(worker->index);
    execute_initial_claims();
    for (;;) {
        if (atomic_load_explicit(
                &remaining_execution_count, memory_order_acquire
            ) == 0) {
            return NULL;
        }
        size_t execution_index;
        if (claim_child_b(worker, &execution_index)) {
            execute_published_branch(execution_index);
            continue;
        }
        processor_relax();
    }
}
#endif

static void run_program(void) {
    initialize_program();
#if DEFINE_LITERAL_STRATEGY == DEFINE_LITERAL_STRATEGY_DIRECT
    for (size_t execution_index = 0;
         execution_index < DEFINE_LITERAL_EXECUTION_COUNT;
         ++execution_index) {
        execute_complete_graph(execution_index);
    }
#else
    pthread_t threads[DEFINE_LITERAL_WORKER_COUNT] = {0};
    for (size_t worker_index = 0;
         worker_index < DEFINE_LITERAL_WORKER_COUNT;
         ++worker_index) {
#if DEFINE_LITERAL_STRATEGY == DEFINE_LITERAL_STRATEGY_DIRECT_RANGES
        int error_number = pthread_create(
            &threads[worker_index],
            NULL,
            run_direct_range,
            &workers[worker_index]
        );
#else
        int error_number = pthread_create(
            &threads[worker_index],
            NULL,
            run_claimable,
            &workers[worker_index]
        );
#endif
        if (error_number != 0) {
            fail_errno("pthread_create", error_number);
        }
    }
    for (size_t worker_index = 0;
         worker_index < DEFINE_LITERAL_WORKER_COUNT;
         ++worker_index) {
        int error_number = pthread_join(threads[worker_index], NULL);
        if (error_number != 0) {
            fail_errno("pthread_join", error_number);
        }
    }
#endif
}

static uint64_t program_checksum(void) {
    uint64_t checksum = 0;
    for (size_t execution_index = 0;
         execution_index < DEFINE_LITERAL_EXECUTION_COUNT;
         ++execution_index) {
        checksum = (checksum ^ action_executions[execution_index].result)
            * UINT64_C(0x100000001b3);
    }
    return checksum;
}

int main(void) {
    run_program();
    printf("checksum=%" PRIu64 "\n", program_checksum());
    return EXIT_SUCCESS;
}
