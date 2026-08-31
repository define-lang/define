#define _GNU_SOURCE

#if !defined(__linux__)
#error "pointer_free_static_benchmark.c requires Linux target runtime facilities"
#endif

#include <errno.h>
#if defined(__i386__) || defined(__x86_64__)
#include <immintrin.h>
#endif
#include <limits.h>
#include <pthread.h>
#include <sched.h>
#include <stdalign.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define POINTER_FREE_GRAPH_CHAIN 1
#define POINTER_FREE_GRAPH_FAN_JOIN 2
#define POINTER_FREE_GRAPH_PARALLEL_CHAINS 3

#define POINTER_FREE_SCHEDULER_STATIC 1
#define POINTER_FREE_SCHEDULER_CURSOR 2
#define POINTER_FREE_SCHEDULER_BYTES 3
#define POINTER_FREE_SCHEDULER_BITS 4
#define POINTER_FREE_SCHEDULER_EXCHANGE 5
#define POINTER_FREE_SCHEDULER_DIRECT 6
#define POINTER_FREE_SCHEDULER_CONTIGUOUS 7
#define POINTER_FREE_SCHEDULER_DIRECT_RANGES 8
#define POINTER_FREE_SCHEDULER_POINTER_TASKS 9

#define POINTER_FREE_PRESENCE_NONE 0
#define POINTER_FREE_PRESENCE_BYTES 1
#define POINTER_FREE_PRESENCE_BITS 2

#if !defined(POINTER_FREE_GRAPH)
#error "define POINTER_FREE_GRAPH to one of the POINTER_FREE_GRAPH_* values"
#endif

#if !defined(POINTER_FREE_SCHEDULER)
#error "define POINTER_FREE_SCHEDULER to one of the POINTER_FREE_SCHEDULER_* values"
#endif

#if !defined(POINTER_FREE_CLAIM_LIMIT)
#define POINTER_FREE_CLAIM_LIMIT 1
#endif

#if !defined(POINTER_FREE_DYNAMIC_CLAIM_LIMIT)
#define POINTER_FREE_DYNAMIC_CLAIM_LIMIT 8
#endif

#if !defined(POINTER_FREE_PRESENCE)
#define POINTER_FREE_PRESENCE POINTER_FREE_PRESENCE_NONE
#endif

#if POINTER_FREE_GRAPH < POINTER_FREE_GRAPH_CHAIN \
    || POINTER_FREE_GRAPH > POINTER_FREE_GRAPH_PARALLEL_CHAINS
#error "invalid pointer-free graph"
#endif

#if POINTER_FREE_SCHEDULER < POINTER_FREE_SCHEDULER_STATIC \
    || POINTER_FREE_SCHEDULER > POINTER_FREE_SCHEDULER_POINTER_TASKS
#error "invalid pointer-free scheduler"
#endif

#if POINTER_FREE_CLAIM_LIMIT < 1 || POINTER_FREE_CLAIM_LIMIT > 64
#error "pointer-free claim limit must be between 1 and 64"
#endif

#if POINTER_FREE_DYNAMIC_CLAIM_LIMIT < 1 \
    || POINTER_FREE_DYNAMIC_CLAIM_LIMIT > 64
#error "pointer-free dynamic claim limit must be between 1 and 64"
#endif

#if POINTER_FREE_PRESENCE < POINTER_FREE_PRESENCE_NONE \
    || POINTER_FREE_PRESENCE > POINTER_FREE_PRESENCE_BITS
#error "invalid pointer-free Particle presence representation"
#endif

enum {
    cache_line_size = 64,
    maximum_workers = 32,
};

#if POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_DIRECT \
    || POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_DIRECT_RANGES
#define POINTER_FREE_SEQUENTIAL_STATE 1
#else
#define POINTER_FREE_SEQUENTIAL_STATE 0
#endif

#if !POINTER_FREE_SEQUENTIAL_STATE \
    && POINTER_FREE_GRAPH != POINTER_FREE_GRAPH_CHAIN
#define POINTER_FREE_CONCURRENT_PARTICLE_OPERATIONS 1
#else
#define POINTER_FREE_CONCURRENT_PARTICLE_OPERATIONS 0
#endif

typedef enum {
    cost_uniform,
    cost_interleaved,
    cost_random,
    cost_clustered,
    cost_late_clustered,
} CostDistribution;

typedef struct {
    size_t execution_count;
    unsigned int fast_work_amount;
    unsigned int slow_work_amount;
    size_t slow_execution_count;
    CostDistribution cost_distribution;
    size_t worker_count;
    size_t warmup_count;
    size_t sample_count;
} BenchmarkParameters;

typedef struct {
#if !POINTER_FREE_SEQUENTIAL_STATE
    alignas(cache_line_size) uint64_t value;
#else
    uint64_t value;
#endif
#if POINTER_FREE_PRESENCE == POINTER_FREE_PRESENCE_BYTES
    unsigned char present;
#endif
} ParticleState;

typedef struct {
#if !POINTER_FREE_SEQUENTIAL_STATE
    alignas(cache_line_size) atomic_uint remaining;
#else
    atomic_uint remaining;
#endif
} JoinState;

#if POINTER_FREE_GRAPH == POINTER_FREE_GRAPH_CHAIN
typedef struct {
    ParticleState particle;
#if POINTER_FREE_PRESENCE == POINTER_FREE_PRESENCE_BITS
#if POINTER_FREE_CONCURRENT_PARTICLE_OPERATIONS
    alignas(cache_line_size) atomic_uchar particle_presence;
#else
    unsigned char particle_presence;
#endif
#endif
#if !POINTER_FREE_SEQUENTIAL_STATE
    alignas(cache_line_size) uint64_t seed;
#else
    uint64_t seed;
#endif
    uint64_t result;
    unsigned int work_amount;
} GraphExecution;
#elif POINTER_FREE_GRAPH == POINTER_FREE_GRAPH_FAN_JOIN
typedef struct {
    ParticleState box;
    ParticleState child_a;
    ParticleState child_b;
#if POINTER_FREE_PRESENCE == POINTER_FREE_PRESENCE_BITS
#if POINTER_FREE_CONCURRENT_PARTICLE_OPERATIONS
    alignas(cache_line_size) atomic_uchar particle_presence;
#else
    unsigned char particle_presence;
#endif
#endif
    JoinState join;
#if !POINTER_FREE_SEQUENTIAL_STATE
    alignas(cache_line_size) uint64_t seed;
#else
    uint64_t seed;
#endif
    uint64_t result;
    unsigned int work_amount;
} GraphExecution;
#else
typedef struct {
    ParticleState local_particle;
    ParticleState trigger_particle;
    ParticleState other_particle;
#if POINTER_FREE_PRESENCE == POINTER_FREE_PRESENCE_BITS
#if POINTER_FREE_CONCURRENT_PARTICLE_OPERATIONS
    alignas(cache_line_size) atomic_uchar particle_presence;
#else
    unsigned char particle_presence;
#endif
#endif
    JoinState join;
#if !POINTER_FREE_SEQUENTIAL_STATE
    alignas(cache_line_size) uint64_t seed;
#else
    uint64_t seed;
#endif
    uint64_t result;
    unsigned int work_amount;
} GraphExecution;
#endif

#if !POINTER_FREE_SEQUENTIAL_STATE
static_assert(
    sizeof(GraphExecution) % cache_line_size == 0,
    "graph executions must not share a cache line"
);
#endif

typedef struct PointerFreeScheduler PointerFreeScheduler;

#if POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_POINTER_TASKS
typedef void (*PointerTaskFunction)(PointerFreeScheduler *, size_t);

typedef struct {
    PointerTaskFunction function;
    size_t task_id;
} PointerTask;
#endif

typedef struct {
    PointerFreeScheduler *scheduler;
    size_t index;
    size_t ready_word_cursor;
    size_t claimed_word_index;
    uint64_t claimed_bits;
} PointerFreeWorker;

struct PointerFreeScheduler {
    GraphExecution *executions;
    size_t execution_count;
    size_t initial_task_count;
    size_t ready_task_base;
    size_t ready_task_count;
    size_t ready_word_count;
    size_t worker_count;
    atomic_size_t next_initial_task;
    atomic_size_t remaining_executions;
    atomic_size_t remaining_workers;
    atomic_bool done;
#if POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_BYTES
    _Atomic unsigned char *ready_bytes;
#else
    _Atomic uint64_t *ready_words;
#endif
#if POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_POINTER_TASKS
    PointerTask *pointer_tasks;
#endif
    PointerFreeWorker workers[maximum_workers];
};

[[noreturn]] static void fail_errno(const char *operation, int error_number) {
    errno = error_number;
    perror(operation);
    exit(EXIT_FAILURE);
}

[[noreturn]] static void fail_message(const char *message) {
    fputs(message, stderr);
    fputc('\n', stderr);
    exit(EXIT_FAILURE);
}

static void *allocate_aligned(size_t alignment, size_t size) {
    void *allocation = NULL;
    int error_number = posix_memalign(&allocation, alignment, size);
    if (error_number != 0) {
        fail_errno("posix_memalign", error_number);
    }
    memset(allocation, 0, size);
    return allocation;
}

static void pin_current_thread(size_t worker_index) {
    cpu_set_t processor_set;
    CPU_ZERO(&processor_set);
    CPU_SET(worker_index, &processor_set);
    int error_number = pthread_setaffinity_np(
        pthread_self(), sizeof(processor_set), &processor_set
    );
    if (error_number != 0) {
        fail_errno("pthread_setaffinity_np", error_number);
    }
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

static uint64_t perform_operation_work(
    uint64_t value, uint64_t salt, unsigned int rounds
) {
    value ^= salt;
    for (unsigned int round = 0; round < rounds; ++round) {
        value ^= value << 13;
        value ^= value >> 7;
        value ^= value << 17;
    }
    return value;
}

static void mark_particle_created(
    GraphExecution *execution, ParticleState *particle, unsigned char bit
) {
#if POINTER_FREE_PRESENCE == POINTER_FREE_PRESENCE_NONE
    (void)execution;
    (void)particle;
    (void)bit;
#elif POINTER_FREE_PRESENCE == POINTER_FREE_PRESENCE_BYTES
    (void)execution;
    (void)bit;
    particle->present = 1;
#elif !POINTER_FREE_CONCURRENT_PARTICLE_OPERATIONS
    (void)particle;
    execution->particle_presence |= bit;
#else
    (void)particle;
    (void)atomic_fetch_or_explicit(
        &execution->particle_presence, bit, memory_order_relaxed
    );
#endif
}

static void mark_particle_destroyed(
    GraphExecution *execution, ParticleState *particle, unsigned char bit
) {
#if POINTER_FREE_PRESENCE == POINTER_FREE_PRESENCE_NONE
    (void)execution;
    (void)particle;
    (void)bit;
#elif POINTER_FREE_PRESENCE == POINTER_FREE_PRESENCE_BYTES
    (void)execution;
    (void)bit;
    particle->present = 0;
#elif !POINTER_FREE_CONCURRENT_PARTICLE_OPERATIONS
    (void)particle;
    execution->particle_presence &= (unsigned char)~bit;
#else
    (void)particle;
    (void)atomic_fetch_and_explicit(
        &execution->particle_presence,
        (unsigned char)~bit,
        memory_order_relaxed
    );
#endif
}

static size_t graph_initial_task_count(size_t execution_count) {
#if POINTER_FREE_GRAPH == POINTER_FREE_GRAPH_PARALLEL_CHAINS
    return execution_count * 2;
#else
    return execution_count;
#endif
}

[[maybe_unused]] static size_t graph_total_task_count(size_t execution_count) {
#if POINTER_FREE_GRAPH == POINTER_FREE_GRAPH_CHAIN
    return execution_count;
#else
    return execution_count * 2;
#endif
}

static void initialize_ready_storage(PointerFreeScheduler *scheduler) {
#if POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_DIRECT \
    || POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_DIRECT_RANGES
    scheduler->ready_task_base = 0;
    scheduler->ready_task_count = 0;
#elif POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_STATIC \
    || POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_CURSOR \
    || POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_CONTIGUOUS \
    || POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_POINTER_TASKS
#if POINTER_FREE_GRAPH == POINTER_FREE_GRAPH_FAN_JOIN
    scheduler->ready_task_base = scheduler->execution_count;
    scheduler->ready_task_count = scheduler->execution_count;
#else
    scheduler->ready_task_base = 0;
    scheduler->ready_task_count = 0;
#endif
#else
    scheduler->ready_task_base = 0;
    scheduler->ready_task_count = graph_total_task_count(
        scheduler->execution_count
    );
#endif
    scheduler->ready_word_count = (scheduler->ready_task_count + 63) / 64;
#if POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_BYTES
    scheduler->ready_bytes = allocate_aligned(
        cache_line_size,
        scheduler->ready_task_count * sizeof(*scheduler->ready_bytes)
    );
    for (size_t index = 0; index < scheduler->ready_task_count; ++index) {
        atomic_init(&scheduler->ready_bytes[index], 0);
    }
#else
    if (scheduler->ready_word_count == 0) {
        scheduler->ready_words = NULL;
        return;
    }
    scheduler->ready_words = allocate_aligned(
        cache_line_size,
        scheduler->ready_word_count * sizeof(*scheduler->ready_words)
    );
    for (size_t index = 0; index < scheduler->ready_word_count; ++index) {
        atomic_init(&scheduler->ready_words[index], 0);
    }
#endif
}

static void destroy_ready_storage(PointerFreeScheduler *scheduler) {
#if POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_BYTES
    free(scheduler->ready_bytes);
#else
    free(scheduler->ready_words);
#endif
}

[[maybe_unused]] static void publish_task(
    PointerFreeScheduler *scheduler, size_t task_id
) {
    size_t ready_index = task_id - scheduler->ready_task_base;
#if POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_BYTES
    atomic_store_explicit(
        &scheduler->ready_bytes[ready_index], 1, memory_order_release
    );
#else
    size_t word_index = ready_index / 64;
    uint64_t bit = UINT64_C(1) << (ready_index % 64);
    (void)atomic_fetch_or_explicit(
        &scheduler->ready_words[word_index], bit, memory_order_acq_rel
    );
#endif
}

[[maybe_unused]] static void publish_initial_tasks(
    PointerFreeScheduler *scheduler
) {
#if POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_BYTES
    for (size_t task_id = 0; task_id < scheduler->initial_task_count;
         ++task_id) {
        atomic_store_explicit(
            &scheduler->ready_bytes[task_id], 1, memory_order_relaxed
        );
    }
#elif POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_BITS \
    || POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_EXCHANGE
    size_t full_words = scheduler->initial_task_count / 64;
    for (size_t word_index = 0; word_index < full_words; ++word_index) {
        atomic_store_explicit(
            &scheduler->ready_words[word_index],
            UINT64_MAX,
            memory_order_relaxed
        );
    }
    size_t remaining_bits = scheduler->initial_task_count % 64;
    if (remaining_bits != 0) {
        atomic_store_explicit(
            &scheduler->ready_words[full_words],
            (UINT64_C(1) << remaining_bits) - 1,
            memory_order_relaxed
        );
    }
#else
    (void)scheduler;
#endif
}

[[maybe_unused]] static uint64_t select_low_bits(uint64_t bits, size_t limit) {
    uint64_t selected = 0;
    for (size_t count = 0; count < limit && bits != 0; ++count) {
        uint64_t bit = bits & (~bits + 1);
        selected |= bit;
        bits ^= bit;
    }
    return selected;
}

static bool claim_ready_task(
    PointerFreeWorker *worker, size_t *claimed_task_id
) {
    PointerFreeScheduler *scheduler = worker->scheduler;
#if POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_BYTES
    if (scheduler->ready_task_count == 0) {
        return false;
    }
    size_t cursor = worker->ready_word_cursor;
    for (size_t offset = 0; offset < scheduler->ready_task_count; ++offset) {
        unsigned char ready = atomic_load_explicit(
            &scheduler->ready_bytes[cursor], memory_order_relaxed
        );
        if (ready != 0
            && atomic_exchange_explicit(
                   &scheduler->ready_bytes[cursor],
                   0,
                   memory_order_acquire
               ) != 0) {
            *claimed_task_id = scheduler->ready_task_base + cursor;
            ++cursor;
            if (cursor == scheduler->ready_task_count) {
                cursor = 0;
            }
            worker->ready_word_cursor = cursor;
            return true;
        }
        ++cursor;
        if (cursor == scheduler->ready_task_count) {
            cursor = 0;
        }
    }
    worker->ready_word_cursor = cursor;
    return false;
#else
    if (worker->claimed_bits != 0) {
        unsigned int bit_index = (unsigned int)__builtin_ctzll(
            worker->claimed_bits
        );
        worker->claimed_bits &= worker->claimed_bits - 1;
        *claimed_task_id = scheduler->ready_task_base
            + worker->claimed_word_index * 64 + bit_index;
        return true;
    }
    if (scheduler->ready_word_count == 0) {
        return false;
    }
    size_t cursor = worker->ready_word_cursor;
    for (size_t offset = 0; offset < scheduler->ready_word_count; ++offset) {
        uint64_t observed = atomic_load_explicit(
            &scheduler->ready_words[cursor], memory_order_relaxed
        );
        while (observed != 0) {
#if POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_EXCHANGE
            uint64_t claimed = atomic_exchange_explicit(
                &scheduler->ready_words[cursor], 0, memory_order_acquire
            );
            if (claimed == 0) {
                break;
            }
#else
#if POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_BITS
            uint64_t claimed = select_low_bits(
                observed, POINTER_FREE_CLAIM_LIMIT
            );
#else
            uint64_t claimed = select_low_bits(
                observed, POINTER_FREE_DYNAMIC_CLAIM_LIMIT
            );
#endif
            uint64_t desired = observed & ~claimed;
            if (!atomic_compare_exchange_weak_explicit(
                    &scheduler->ready_words[cursor],
                    &observed,
                    desired,
                    memory_order_acquire,
                    memory_order_relaxed
                )) {
                continue;
            }
#endif
            unsigned int bit_index = (unsigned int)__builtin_ctzll(claimed);
            worker->claimed_bits = claimed & (claimed - 1);
            worker->claimed_word_index = cursor;
            *claimed_task_id = scheduler->ready_task_base + cursor * 64
                + bit_index;
            ++cursor;
            if (cursor == scheduler->ready_word_count) {
                cursor = 0;
            }
            worker->ready_word_cursor = cursor;
            return true;
        }
        ++cursor;
        if (cursor == scheduler->ready_word_count) {
            cursor = 0;
        }
    }
    worker->ready_word_cursor = cursor;
    return false;
#endif
}

static void finish_graph_execution(
    PointerFreeScheduler *scheduler, GraphExecution *execution, uint64_t result
) {
    execution->result = result;
#if POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_DIRECT \
    || POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_DIRECT_RANGES
    (void)scheduler;
#else
    if (atomic_fetch_sub_explicit(
            &scheduler->remaining_executions, 1, memory_order_acq_rel
        ) == 1) {
        atomic_store_explicit(&scheduler->done, true, memory_order_release);
    }
#endif
}

#if POINTER_FREE_GRAPH == POINTER_FREE_GRAPH_CHAIN
static void execute_chain(
    PointerFreeScheduler *scheduler, size_t execution_index
) {
    GraphExecution *execution = &scheduler->executions[execution_index];
    ParticleState *particle = &execution->particle;

    mark_particle_created(execution, particle, 1);
    particle->value = perform_operation_work(
        execution->seed,
        UINT64_C(0x243f6a8885a308d3),
        execution->work_amount
    );
    particle->value = perform_operation_work(
        particle->value,
        UINT64_C(0x13198a2e03707344),
        execution->work_amount
    );
    particle->value = perform_operation_work(
        particle->value,
        UINT64_C(0xa4093822299f31d0),
        execution->work_amount
    );
    mark_particle_destroyed(execution, particle, 1);
#if POINTER_FREE_PRESENCE == POINTER_FREE_PRESENCE_BYTES
    uint64_t presence = particle->present;
#elif POINTER_FREE_PRESENCE == POINTER_FREE_PRESENCE_BITS
#if !POINTER_FREE_CONCURRENT_PARTICLE_OPERATIONS
    uint64_t presence = execution->particle_presence;
#else
    uint64_t presence = atomic_load_explicit(
        &execution->particle_presence, memory_order_relaxed
    );
#endif
#else
    uint64_t presence = 0;
#endif
    finish_graph_execution(
        scheduler, execution, particle->value ^ presence
    );
}
#elif POINTER_FREE_GRAPH == POINTER_FREE_GRAPH_FAN_JOIN
static void complete_fan_join(
    PointerFreeScheduler *scheduler, GraphExecution *execution
) {
    execution->box.value = perform_operation_work(
        execution->box.value ^ execution->child_a.value
            ^ (execution->child_b.value << 1),
        UINT64_C(0x082efa98ec4e6c89),
        execution->work_amount
    );
    mark_particle_destroyed(execution, &execution->box, 1);
#if POINTER_FREE_PRESENCE == POINTER_FREE_PRESENCE_BYTES
    uint64_t presence = (uint64_t)execution->box.present
        | ((uint64_t)execution->child_a.present << 1)
        | ((uint64_t)execution->child_b.present << 2);
#elif POINTER_FREE_PRESENCE == POINTER_FREE_PRESENCE_BITS
#if !POINTER_FREE_CONCURRENT_PARTICLE_OPERATIONS
    uint64_t presence = execution->particle_presence;
#else
    uint64_t presence = atomic_load_explicit(
        &execution->particle_presence, memory_order_relaxed
    );
#endif
#else
    uint64_t presence = 0;
#endif
    finish_graph_execution(
        scheduler, execution, execution->box.value ^ presence
    );
}

static void run_fan_join_child_a(GraphExecution *execution) {
    mark_particle_created(execution, &execution->child_a, 2);
    execution->child_a.value = perform_operation_work(
        execution->seed,
        UINT64_C(0x452821e638d01377),
        execution->work_amount
    );
    execution->child_a.value = perform_operation_work(
        execution->child_a.value,
        UINT64_C(0xbe5466cf34e90c6c),
        execution->work_amount
    );
    mark_particle_destroyed(execution, &execution->child_a, 2);
}

static void run_fan_join_child_b(GraphExecution *execution) {
    mark_particle_created(execution, &execution->child_b, 4);
    execution->child_b.value = perform_operation_work(
        execution->seed,
        UINT64_C(0xc0ac29b7c97c50dd),
        execution->work_amount
    );
    mark_particle_destroyed(execution, &execution->child_b, 4);
    execution->child_b.value = perform_operation_work(
        execution->child_b.value,
        UINT64_C(0x3f84d5b5b5470917),
        execution->work_amount
    );
}

static void finish_fan_join_branch(
    PointerFreeScheduler *scheduler, GraphExecution *execution
) {
    if (atomic_fetch_sub_explicit(
            &execution->join.remaining, 1, memory_order_acq_rel
        ) == 1) {
        complete_fan_join(scheduler, execution);
    }
}

static void execute_fan_join_child_a(
    PointerFreeScheduler *scheduler, GraphExecution *execution
) {
    run_fan_join_child_a(execution);
    finish_fan_join_branch(scheduler, execution);
}

static void execute_fan_join_child_b(
    PointerFreeScheduler *scheduler, GraphExecution *execution
) {
    run_fan_join_child_b(execution);
    finish_fan_join_branch(scheduler, execution);
}

static void execute_fan_join_root(
    PointerFreeScheduler *scheduler, size_t execution_index
) {
    GraphExecution *execution = &scheduler->executions[execution_index];
    mark_particle_created(execution, &execution->box, 1);
    execution->box.value = perform_operation_work(
        execution->seed,
        UINT64_C(0x243f6a8885a308d3),
        execution->work_amount
    );
    publish_task(
        scheduler, scheduler->execution_count + execution_index
    );
    execute_fan_join_child_a(scheduler, execution);
}
#else
static void complete_parallel_chains(
    PointerFreeScheduler *scheduler, GraphExecution *execution
) {
#if POINTER_FREE_PRESENCE == POINTER_FREE_PRESENCE_BYTES
    uint64_t presence = (uint64_t)execution->local_particle.present
        | ((uint64_t)execution->trigger_particle.present << 1)
        | ((uint64_t)execution->other_particle.present << 2);
#elif POINTER_FREE_PRESENCE == POINTER_FREE_PRESENCE_BITS
#if !POINTER_FREE_CONCURRENT_PARTICLE_OPERATIONS
    uint64_t presence = execution->particle_presence;
#else
    uint64_t presence = atomic_load_explicit(
        &execution->particle_presence, memory_order_relaxed
    );
#endif
#else
    uint64_t presence = 0;
#endif
    uint64_t result = execution->local_particle.value
        ^ (execution->trigger_particle.value << 1)
        ^ (execution->other_particle.value << 2) ^ presence;
    finish_graph_execution(scheduler, execution, result);
}

static void run_local_chain(GraphExecution *execution) {
    mark_particle_created(execution, &execution->local_particle, 1);
    execution->local_particle.value = perform_operation_work(
        execution->seed,
        UINT64_C(0x243f6a8885a308d3),
        execution->work_amount
    );
    execution->local_particle.value = perform_operation_work(
        execution->local_particle.value,
        UINT64_C(0x13198a2e03707344),
        execution->work_amount
    );
    mark_particle_destroyed(execution, &execution->local_particle, 1);
}

static void run_triggered_chain(GraphExecution *execution) {
    mark_particle_created(execution, &execution->trigger_particle, 2);
    execution->trigger_particle.value = perform_operation_work(
        execution->seed,
        UINT64_C(0xa4093822299f31d0),
        execution->work_amount
    );
    mark_particle_created(execution, &execution->other_particle, 4);
    execution->other_particle.value = perform_operation_work(
        execution->trigger_particle.value,
        UINT64_C(0x082efa98ec4e6c89),
        execution->work_amount
    );
    mark_particle_destroyed(execution, &execution->other_particle, 4);
    mark_particle_destroyed(execution, &execution->trigger_particle, 2);
    execution->other_particle.value = perform_operation_work(
        execution->other_particle.value,
        UINT64_C(0x452821e638d01377),
        execution->work_amount
    );
}

static void finish_parallel_chain(
    PointerFreeScheduler *scheduler, GraphExecution *execution
) {
    if (atomic_fetch_sub_explicit(
            &execution->join.remaining, 1, memory_order_acq_rel
        ) == 1) {
        complete_parallel_chains(scheduler, execution);
    }
}

static void execute_local_chain(
    PointerFreeScheduler *scheduler, size_t execution_index
) {
    GraphExecution *execution = &scheduler->executions[execution_index];
    run_local_chain(execution);
    finish_parallel_chain(scheduler, execution);
}

static void execute_triggered_chain(
    PointerFreeScheduler *scheduler, size_t execution_index
) {
    GraphExecution *execution = &scheduler->executions[execution_index];
    run_triggered_chain(execution);
    finish_parallel_chain(scheduler, execution);
}
#endif

static void execute_task(PointerFreeScheduler *scheduler, size_t task_id) {
#if POINTER_FREE_GRAPH == POINTER_FREE_GRAPH_CHAIN
    execute_chain(scheduler, task_id);
#elif POINTER_FREE_GRAPH == POINTER_FREE_GRAPH_FAN_JOIN
    if (task_id < scheduler->execution_count) {
        execute_fan_join_root(scheduler, task_id);
    } else {
        execute_fan_join_child_b(
            scheduler,
            &scheduler->executions[task_id - scheduler->execution_count]
        );
    }
#else
    if (task_id < scheduler->execution_count) {
        execute_local_chain(scheduler, task_id);
    } else {
        execute_triggered_chain(
            scheduler, task_id - scheduler->execution_count
        );
    }
#endif
}

static void initialize_pointer_tasks(PointerFreeScheduler *scheduler) {
#if POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_POINTER_TASKS
    scheduler->pointer_tasks = allocate_aligned(
        cache_line_size,
        scheduler->initial_task_count * sizeof(*scheduler->pointer_tasks)
    );
#if POINTER_FREE_GRAPH == POINTER_FREE_GRAPH_CHAIN
    for (size_t execution_index = 0;
         execution_index < scheduler->execution_count;
         ++execution_index) {
        scheduler->pointer_tasks[execution_index] = (PointerTask){
            .function = execute_chain,
            .task_id = execution_index,
        };
    }
#elif POINTER_FREE_GRAPH == POINTER_FREE_GRAPH_FAN_JOIN
    for (size_t execution_index = 0;
         execution_index < scheduler->execution_count;
         ++execution_index) {
        scheduler->pointer_tasks[execution_index] = (PointerTask){
            .function = execute_fan_join_root,
            .task_id = execution_index,
        };
    }
#else
    for (size_t execution_index = 0;
         execution_index < scheduler->execution_count;
         ++execution_index) {
        scheduler->pointer_tasks[execution_index] = (PointerTask){
            .function = execute_local_chain,
            .task_id = execution_index,
        };
        scheduler->pointer_tasks[
            scheduler->execution_count + execution_index
        ] = (PointerTask){
            .function = execute_triggered_chain,
            .task_id = execution_index,
        };
    }
#endif
#else
    (void)scheduler;
#endif
}

static void execute_direct_graph_range(
    PointerFreeScheduler *scheduler, size_t first_execution, size_t limit
) {
    for (size_t execution_index = first_execution;
         execution_index < limit;
         ++execution_index) {
#if POINTER_FREE_GRAPH == POINTER_FREE_GRAPH_CHAIN
        execute_chain(scheduler, execution_index);
#elif POINTER_FREE_GRAPH == POINTER_FREE_GRAPH_FAN_JOIN
        GraphExecution *execution = &scheduler->executions[execution_index];
        mark_particle_created(execution, &execution->box, 1);
        execution->box.value = perform_operation_work(
            execution->seed,
            UINT64_C(0x243f6a8885a308d3),
            execution->work_amount
        );
        run_fan_join_child_a(execution);
        run_fan_join_child_b(execution);
        complete_fan_join(scheduler, execution);
#else
        GraphExecution *execution = &scheduler->executions[execution_index];
        run_local_chain(execution);
        run_triggered_chain(execution);
        complete_parallel_chains(scheduler, execution);
#endif
    }
}

[[maybe_unused]] static void execute_direct_graphs(
    PointerFreeScheduler *scheduler
) {
    execute_direct_graph_range(scheduler, 0, scheduler->execution_count);
}

[[maybe_unused]] static void execute_statically_assigned_tasks(
    PointerFreeWorker *worker
) {
    PointerFreeScheduler *scheduler = worker->scheduler;
    for (size_t task_id = worker->index;
         task_id < scheduler->initial_task_count;
         task_id += scheduler->worker_count) {
        execute_task(scheduler, task_id);
    }
}

[[maybe_unused]] static void execute_cursor_tasks(
    PointerFreeWorker *worker
) {
    PointerFreeScheduler *scheduler = worker->scheduler;
    for (;;) {
        size_t first_task = atomic_fetch_add_explicit(
            &scheduler->next_initial_task,
            POINTER_FREE_CLAIM_LIMIT,
            memory_order_relaxed
        );
        if (first_task >= scheduler->initial_task_count) {
            return;
        }
        size_t task_limit = first_task + POINTER_FREE_CLAIM_LIMIT;
        if (task_limit > scheduler->initial_task_count) {
            task_limit = scheduler->initial_task_count;
        }
        for (size_t task_id = first_task; task_id < task_limit; ++task_id) {
            execute_task(scheduler, task_id);
        }
    }
}

#if POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_POINTER_TASKS
static void execute_pointer_tasks(
    PointerFreeWorker *worker
) {
    PointerFreeScheduler *scheduler = worker->scheduler;
    for (;;) {
        size_t first_task = atomic_fetch_add_explicit(
            &scheduler->next_initial_task,
            POINTER_FREE_CLAIM_LIMIT,
            memory_order_relaxed
        );
        if (first_task >= scheduler->initial_task_count) {
            return;
        }
        size_t task_limit = first_task + POINTER_FREE_CLAIM_LIMIT;
        if (task_limit > scheduler->initial_task_count) {
            task_limit = scheduler->initial_task_count;
        }
        for (size_t task_index = first_task; task_index < task_limit;
             ++task_index) {
            const PointerTask *task = &scheduler->pointer_tasks[task_index];
            task->function(scheduler, task->task_id);
        }
    }
}
#endif

[[maybe_unused]] static void execute_contiguous_tasks(
    PointerFreeWorker *worker
) {
    PointerFreeScheduler *scheduler = worker->scheduler;
    size_t first_task = scheduler->initial_task_count * worker->index
        / scheduler->worker_count;
    size_t task_limit = scheduler->initial_task_count * (worker->index + 1)
        / scheduler->worker_count;
    for (size_t task_id = first_task; task_id < task_limit; ++task_id) {
        execute_task(scheduler, task_id);
    }
}

[[maybe_unused]] static void execute_direct_range(
    PointerFreeWorker *worker
) {
    PointerFreeScheduler *scheduler = worker->scheduler;
    size_t first_execution = scheduler->execution_count * worker->index
        / scheduler->worker_count;
    size_t execution_limit = scheduler->execution_count * (worker->index + 1)
        / scheduler->worker_count;
    execute_direct_graph_range(scheduler, first_execution, execution_limit);
}

[[maybe_unused]] static void *run_worker(void *opaque_worker) {
    PointerFreeWorker *worker = opaque_worker;
    PointerFreeScheduler *scheduler = worker->scheduler;
    pin_current_thread(worker->index);

#if POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_STATIC
    execute_statically_assigned_tasks(worker);
#elif POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_CURSOR
    execute_cursor_tasks(worker);
#elif POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_POINTER_TASKS
    execute_pointer_tasks(worker);
#elif POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_CONTIGUOUS
    execute_contiguous_tasks(worker);
#elif POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_DIRECT_RANGES
    execute_direct_range(worker);
    if (atomic_fetch_sub_explicit(
            &scheduler->remaining_workers, 1, memory_order_acq_rel
        ) == 1) {
        atomic_store_explicit(&scheduler->done, true, memory_order_release);
    }
    return NULL;
#endif

    for (;;) {
        if (atomic_load_explicit(&scheduler->done, memory_order_acquire)) {
            return NULL;
        }
        size_t task_id;
        if (claim_ready_task(worker, &task_id)) {
            execute_task(scheduler, task_id);
            continue;
        }
        processor_relax();
    }
}

static uint64_t monotonic_nanoseconds(void) {
    struct timespec time;
    if (clock_gettime(CLOCK_MONOTONIC_RAW, &time) != 0) {
        fail_message("clock_gettime failed");
    }
    return (uint64_t)time.tv_sec * UINT64_C(1000000000)
        + (uint64_t)time.tv_nsec;
}

static uint64_t next_shuffle_random(uint64_t *state) {
    *state ^= *state << 13;
    *state ^= *state >> 7;
    *state ^= *state << 17;
    return *state;
}

static void assign_work_amounts(
    PointerFreeScheduler *scheduler, const BenchmarkParameters *parameters
) {
    for (size_t index = 0; index < scheduler->execution_count; ++index) {
        scheduler->executions[index].work_amount =
            parameters->fast_work_amount;
    }
    if (parameters->slow_execution_count == 0) {
        return;
    }
    if (parameters->cost_distribution == cost_clustered) {
        for (size_t index = 0; index < parameters->slow_execution_count;
             ++index) {
            scheduler->executions[index].work_amount =
                parameters->slow_work_amount;
        }
        return;
    }
    if (parameters->cost_distribution == cost_late_clustered) {
        size_t first_slow = scheduler->execution_count
            - parameters->slow_execution_count;
        for (size_t index = first_slow; index < scheduler->execution_count;
             ++index) {
            scheduler->executions[index].work_amount =
                parameters->slow_work_amount;
        }
        return;
    }
    if (parameters->cost_distribution == cost_interleaved) {
        size_t accumulator = 0;
        for (size_t index = 0; index < scheduler->execution_count; ++index) {
            accumulator += parameters->slow_execution_count;
            if (accumulator >= scheduler->execution_count) {
                scheduler->executions[index].work_amount =
                    parameters->slow_work_amount;
                accumulator -= scheduler->execution_count;
            }
        }
        return;
    }
    for (size_t index = 0; index < parameters->slow_execution_count; ++index) {
        scheduler->executions[index].work_amount =
            parameters->slow_work_amount;
    }
    uint64_t random_state = UINT64_C(0xd1b54a32d192ed03);
    for (size_t remaining = scheduler->execution_count; remaining > 1;
         --remaining) {
        size_t swap_index = (size_t)(
            next_shuffle_random(&random_state) % remaining
        );
        unsigned int work_amount =
            scheduler->executions[remaining - 1].work_amount;
        scheduler->executions[remaining - 1].work_amount =
            scheduler->executions[swap_index].work_amount;
        scheduler->executions[swap_index].work_amount = work_amount;
    }
}

static void initialize_graph_executions(
    PointerFreeScheduler *scheduler, const BenchmarkParameters *parameters
) {
    for (size_t index = 0; index < scheduler->execution_count; ++index) {
        GraphExecution *execution = &scheduler->executions[index];
        execution->seed = UINT64_C(0x9e3779b97f4a7c15) + index;
#if POINTER_FREE_PRESENCE == POINTER_FREE_PRESENCE_BITS \
    && POINTER_FREE_CONCURRENT_PARTICLE_OPERATIONS
        atomic_init(&execution->particle_presence, 0);
#endif
#if POINTER_FREE_GRAPH != POINTER_FREE_GRAPH_CHAIN
        atomic_init(&execution->join.remaining, 2);
#endif
    }
    assign_work_amounts(scheduler, parameters);
}

static void initialize_scheduler(
    PointerFreeScheduler *scheduler, const BenchmarkParameters *parameters
) {
    memset(scheduler, 0, sizeof(*scheduler));
    scheduler->execution_count = parameters->execution_count;
    scheduler->initial_task_count = graph_initial_task_count(
        parameters->execution_count
    );
    scheduler->worker_count = parameters->worker_count;
    scheduler->executions = allocate_aligned(
        cache_line_size,
        parameters->execution_count * sizeof(*scheduler->executions)
    );
    initialize_graph_executions(scheduler, parameters);
    initialize_ready_storage(scheduler);
    initialize_pointer_tasks(scheduler);
    atomic_init(&scheduler->next_initial_task, 0);
    atomic_init(
        &scheduler->remaining_executions, parameters->execution_count
    );
    atomic_init(&scheduler->remaining_workers, parameters->worker_count);
    atomic_init(&scheduler->done, false);
    for (size_t index = 0; index < scheduler->worker_count; ++index) {
        scheduler->workers[index] = (PointerFreeWorker){
            .scheduler = scheduler,
            .index = index,
            .ready_word_cursor = scheduler->ready_word_count == 0
                ? 0
                : index % scheduler->ready_word_count,
        };
    }
}

static void destroy_scheduler(PointerFreeScheduler *scheduler) {
    destroy_ready_storage(scheduler);
#if POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_POINTER_TASKS
    free(scheduler->pointer_tasks);
#endif
    free(scheduler->executions);
}

static uint64_t run_benchmark_sample(
    const BenchmarkParameters *parameters,
    uint64_t *checksum,
    uint64_t *expected_sample_checksum,
    bool *has_expected_sample_checksum
) {
    PointerFreeScheduler scheduler;
    initialize_scheduler(&scheduler, parameters);

#if POINTER_FREE_SCHEDULER != POINTER_FREE_SCHEDULER_DIRECT
    pthread_t threads[maximum_workers] = {0};
#endif
    uint64_t start = monotonic_nanoseconds();
#if POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_DIRECT
    execute_direct_graphs(&scheduler);
#else
    publish_initial_tasks(&scheduler);
    for (size_t index = 0; index < scheduler.worker_count; ++index) {
        int error_number = pthread_create(
            &threads[index], NULL, run_worker, &scheduler.workers[index]
        );
        if (error_number != 0) {
            fail_errno("pthread_create", error_number);
        }
    }
    for (size_t index = 0; index < scheduler.worker_count; ++index) {
        int error_number = pthread_join(threads[index], NULL);
        if (error_number != 0) {
            fail_errno("pthread_join", error_number);
        }
    }
#endif
    uint64_t elapsed = monotonic_nanoseconds() - start;

    uint64_t sample_checksum = 0;
    for (size_t index = 0; index < scheduler.execution_count; ++index) {
        sample_checksum = (
            sample_checksum ^ scheduler.executions[index].result
        ) * UINT64_C(0x100000001b3);
    }
    if (*has_expected_sample_checksum
        && sample_checksum != *expected_sample_checksum) {
        fail_message("benchmark result changed between samples");
    }
    *expected_sample_checksum = sample_checksum;
    *has_expected_sample_checksum = true;
    *checksum += sample_checksum;
    destroy_scheduler(&scheduler);
    return elapsed;
}

static int compare_uint64(const void *left, const void *right) {
    uint64_t left_value = *(const uint64_t *)left;
    uint64_t right_value = *(const uint64_t *)right;
    return (left_value > right_value) - (left_value < right_value);
}

static unsigned long parse_unsigned_argument(
    const char *argument, const char *name
) {
    if (argument[0] == '-') {
        fprintf(stderr, "%s must be an unsigned integer\n", name);
        exit(EXIT_FAILURE);
    }
    char *end = NULL;
    errno = 0;
    unsigned long value = strtoul(argument, &end, 10);
    if (errno != 0 || end == argument || *end != '\0') {
        fprintf(stderr, "%s must be an unsigned integer\n", name);
        exit(EXIT_FAILURE);
    }
    return value;
}

static CostDistribution parse_cost_distribution(const char *name) {
    if (strcmp(name, "uniform") == 0) {
        return cost_uniform;
    }
    if (strcmp(name, "interleaved") == 0) {
        return cost_interleaved;
    }
    if (strcmp(name, "random") == 0) {
        return cost_random;
    }
    if (strcmp(name, "clustered") == 0) {
        return cost_clustered;
    }
    if (strcmp(name, "late") == 0) {
        return cost_late_clustered;
    }
    fail_message("unknown cost distribution");
    return cost_uniform;
}

static const char *graph_name(void) {
#if POINTER_FREE_GRAPH == POINTER_FREE_GRAPH_CHAIN
    return "chain";
#elif POINTER_FREE_GRAPH == POINTER_FREE_GRAPH_FAN_JOIN
    return "fan-join";
#else
    return "parallel-chains";
#endif
}

static const char *scheduler_name(void) {
#if POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_STATIC
    return "static";
#elif POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_CURSOR
    return "cursor";
#elif POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_BYTES
    return "bytes";
#elif POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_BITS
    return "bits";
#elif POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_EXCHANGE
    return "exchange";
#elif POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_DIRECT
    return "direct";
#elif POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_CONTIGUOUS
    return "contiguous";
#elif POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_DIRECT_RANGES
    return "direct-ranges";
#else
    return "pointer-tasks";
#endif
}

static size_t benchmark_readiness_bytes(size_t execution_count) {
    size_t ready_task_count = 0;
#if POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_DIRECT \
    || POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_DIRECT_RANGES
    (void)execution_count;
#elif POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_STATIC \
    || POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_CURSOR \
    || POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_CONTIGUOUS \
    || POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_POINTER_TASKS
#if POINTER_FREE_GRAPH == POINTER_FREE_GRAPH_FAN_JOIN
    ready_task_count = execution_count;
#else
    (void)execution_count;
#endif
#else
    ready_task_count = graph_total_task_count(execution_count);
#endif
#if POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_BYTES
    return ready_task_count;
#else
    return ((ready_task_count + 63) / 64) * sizeof(uint64_t);
#endif
}

static size_t benchmark_task_table_bytes(size_t execution_count) {
#if POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_POINTER_TASKS
    return graph_initial_task_count(execution_count) * sizeof(PointerTask);
#else
    (void)execution_count;
    return 0;
#endif
}

static void validate_parameters(const BenchmarkParameters *parameters) {
    if (parameters->execution_count == 0 || parameters->sample_count == 0) {
        fail_message("execution and sample counts must be nonzero");
    }
    if (parameters->worker_count == 0
        || parameters->worker_count > maximum_workers) {
        fail_message("worker count is invalid");
    }
#if POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_DIRECT
    if (parameters->worker_count != 1) {
        fail_message("direct execution requires one worker");
    }
#endif
    if (parameters->execution_count > SIZE_MAX / 2) {
        fail_message(
            "execution count is too large for static runnable identities"
        );
    }
    if (graph_total_task_count(parameters->execution_count) > SIZE_MAX - 63) {
        fail_message("readiness word count overflows size_t");
    }
    if (parameters->execution_count
        > SIZE_MAX / sizeof(GraphExecution)) {
        fail_message("graph execution allocation size overflows size_t");
    }
#if POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_POINTER_TASKS
    if (graph_initial_task_count(parameters->execution_count)
        > SIZE_MAX / sizeof(PointerTask)) {
        fail_message("pointer task allocation size overflows size_t");
    }
#endif
    if (parameters->sample_count > SIZE_MAX / sizeof(uint64_t)) {
        fail_message("sample allocation size overflows size_t");
    }
    if (parameters->slow_execution_count > parameters->execution_count) {
        fail_message("slow execution count exceeds execution count");
    }
    if (parameters->cost_distribution == cost_uniform
        && parameters->slow_execution_count != 0) {
        fail_message("uniform cost requires zero slow executions");
    }
    if (parameters->cost_distribution != cost_uniform
        && parameters->slow_execution_count == 0) {
        fail_message("mixed cost requires slow executions");
    }
    if (parameters->slow_work_amount < parameters->fast_work_amount) {
        fail_message("slow work must not be less than fast work");
    }
}

int main(int argument_count, char **arguments) {
    if (argument_count != 9) {
        fail_message(
            "usage: benchmark executions fast-work slow-work slow-executions "
            "distribution workers warmups samples"
        );
    }
    unsigned long execution_count = parse_unsigned_argument(
        arguments[1], "executions"
    );
    unsigned long fast_work_amount = parse_unsigned_argument(
        arguments[2], "fast-work"
    );
    unsigned long slow_work_amount = parse_unsigned_argument(
        arguments[3], "slow-work"
    );
    unsigned long slow_execution_count = parse_unsigned_argument(
        arguments[4], "slow-executions"
    );
    unsigned long worker_count = parse_unsigned_argument(
        arguments[6], "workers"
    );
    unsigned long warmup_count = parse_unsigned_argument(
        arguments[7], "warmups"
    );
    unsigned long sample_count = parse_unsigned_argument(
        arguments[8], "samples"
    );
    if (execution_count > SIZE_MAX || fast_work_amount > UINT_MAX
        || slow_work_amount > UINT_MAX || slow_execution_count > SIZE_MAX
        || worker_count > SIZE_MAX || warmup_count > SIZE_MAX
        || sample_count > SIZE_MAX) {
        fail_message("benchmark argument exceeds its supported range");
    }
    BenchmarkParameters parameters = {
        .execution_count = (size_t)execution_count,
        .fast_work_amount = (unsigned int)fast_work_amount,
        .slow_work_amount = (unsigned int)slow_work_amount,
        .slow_execution_count = (size_t)slow_execution_count,
        .cost_distribution = parse_cost_distribution(arguments[5]),
        .worker_count = (size_t)worker_count,
        .warmup_count = (size_t)warmup_count,
        .sample_count = (size_t)sample_count,
    };
    validate_parameters(&parameters);
#if POINTER_FREE_SCHEDULER == POINTER_FREE_SCHEDULER_DIRECT
    pin_current_thread(0);
#endif

    uint64_t checksum = 0;
    uint64_t expected_sample_checksum = 0;
    bool has_expected_sample_checksum = false;
    for (size_t warmup = 0; warmup < parameters.warmup_count; ++warmup) {
        (void)run_benchmark_sample(
            &parameters,
            &checksum,
            &expected_sample_checksum,
            &has_expected_sample_checksum
        );
    }
    uint64_t *samples = calloc(parameters.sample_count, sizeof(*samples));
    if (samples == NULL) {
        fail_message("sample allocation failed");
    }
    for (size_t sample = 0; sample < parameters.sample_count; ++sample) {
        samples[sample] = run_benchmark_sample(
            &parameters,
            &checksum,
            &expected_sample_checksum,
            &has_expected_sample_checksum
        );
    }
    qsort(samples, parameters.sample_count, sizeof(*samples), compare_uint64);
    size_t p90_index = (parameters.sample_count / 10) * 9
        + ((parameters.sample_count % 10) * 9) / 10;
    if (p90_index == parameters.sample_count) {
        p90_index = parameters.sample_count - 1;
    }
    printf(
        "graph=%s scheduler=%s claim=%d dynamic_claim=%d presence=%d "
        "execution_bytes=%zu readiness_bytes=%zu task_table_bytes=%zu "
        "min_ns=%lu median_ns=%lu p90_ns=%lu ns_per_execution=%.3f "
        "checksum=%lu\n",
        graph_name(),
        scheduler_name(),
        POINTER_FREE_CLAIM_LIMIT,
        POINTER_FREE_DYNAMIC_CLAIM_LIMIT,
        POINTER_FREE_PRESENCE,
        sizeof(GraphExecution),
        benchmark_readiness_bytes(parameters.execution_count),
        benchmark_task_table_bytes(parameters.execution_count),
        (unsigned long)samples[0],
        (unsigned long)samples[parameters.sample_count / 2],
        (unsigned long)samples[p90_index],
        (double)samples[parameters.sample_count / 2]
            / (double)parameters.execution_count,
        (unsigned long)checksum
    );
    free(samples);
    return EXIT_SUCCESS;
}
