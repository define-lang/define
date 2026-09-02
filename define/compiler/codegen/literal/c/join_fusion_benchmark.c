#define _GNU_SOURCE

#if !defined(__linux__)
#error "join_fusion_benchmark.c requires Linux target runtime facilities"
#endif

#include <errno.h>
#include <pthread.h>
#include <sched.h>
#include <stdalign.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#if defined(LITERAL_C_GEM5_ROI)
#include <gem5/m5ops.h>
#endif

#define JOIN_FUSION_FLAT_COMPACT 1
#define JOIN_FUSION_FLAT_ISOLATED 2
#define JOIN_FUSION_PACKED 3
#define JOIN_FUSION_PACKED_COMPACT 4

#if !defined(JOIN_FUSION_REPRESENTATION)
#error "define JOIN_FUSION_REPRESENTATION to one of the JOIN_FUSION_* values"
#endif

#if !defined(JOIN_FUSION_JOIN_COUNT)
#define JOIN_FUSION_JOIN_COUNT 8
#endif

#if !defined(JOIN_FUSION_PUBLISH_READINESS)
#define JOIN_FUSION_PUBLISH_READINESS 0
#endif

#if !defined(JOIN_FUSION_BATCH_SATISFIED)
#define JOIN_FUSION_BATCH_SATISFIED JOIN_FUSION_PUBLISH_READINESS
#endif

#if JOIN_FUSION_JOIN_COUNT != 1 && JOIN_FUSION_JOIN_COUNT != 2 \
    && JOIN_FUSION_JOIN_COUNT != 4 && JOIN_FUSION_JOIN_COUNT != 8
#error "JOIN_FUSION_JOIN_COUNT must be 1, 2, 4, or 8"
#endif

#if JOIN_FUSION_PUBLISH_READINESS != 0 && JOIN_FUSION_PUBLISH_READINESS != 1
#error "JOIN_FUSION_PUBLISH_READINESS must be zero or one"
#endif

#if JOIN_FUSION_BATCH_SATISFIED != 0 && JOIN_FUSION_BATCH_SATISFIED != 1
#error "JOIN_FUSION_BATCH_SATISFIED must be zero or one"
#endif

#if JOIN_FUSION_PUBLISH_READINESS && !JOIN_FUSION_BATCH_SATISFIED
#error "readiness publication requires batched satisfaction"
#endif

enum {
    cache_line_size = 64,
    predecessor_count = 8,
    join_fan_in = 4,
    maximum_workers = 32,
};

typedef struct {
    alignas(cache_line_size) atomic_uint remaining;
} IsolatedJoin;

typedef struct {
#if JOIN_FUSION_REPRESENTATION == JOIN_FUSION_FLAT_COMPACT
    atomic_uchar joins[JOIN_FUSION_JOIN_COUNT];
#elif JOIN_FUSION_REPRESENTATION == JOIN_FUSION_FLAT_ISOLATED
    IsolatedJoin joins[JOIN_FUSION_JOIN_COUNT];
#elif JOIN_FUSION_REPRESENTATION == JOIN_FUSION_PACKED
    alignas(cache_line_size) atomic_uint_fast64_t packed_joins;
#elif JOIN_FUSION_REPRESENTATION == JOIN_FUSION_PACKED_COMPACT
    atomic_uint_fast64_t packed_joins;
#else
#error "invalid JOIN_FUSION_REPRESENTATION"
#endif
#if JOIN_FUSION_PUBLISH_READINESS
    atomic_uint_fast64_t ready_joins;
#endif
    uint64_t results[JOIN_FUSION_JOIN_COUNT];
} ActionExecution;

typedef struct Benchmark Benchmark;

typedef struct {
    Benchmark *benchmark;
    size_t worker_index;
} Worker;

struct Benchmark {
    ActionExecution *executions;
    size_t execution_count;
    size_t worker_count;
    unsigned int work_amount;
    pthread_barrier_t ready_barrier;
    atomic_bool start;
    Worker workers[maximum_workers];
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

static size_t parse_size(const char *text, const char *name) {
    char *end = NULL;
    errno = 0;
    unsigned long long value = strtoull(text, &end, 10);
    if (errno != 0 || end == text || *end != '\0' || value > SIZE_MAX) {
        fprintf(stderr, "invalid %s: %s\n", name, text);
        exit(EXIT_FAILURE);
    }
    return (size_t)value;
}

static unsigned int parse_unsigned(const char *text, const char *name) {
    size_t value = parse_size(text, name);
    if (value > UINT32_MAX) {
        fprintf(stderr, "%s is too large: %s\n", name, text);
        exit(EXIT_FAILURE);
    }
    return (unsigned int)value;
}

static void *allocate_executions(size_t count, size_t element_size) {
    if (count > SIZE_MAX / element_size) {
        fail_message("Action Execution allocation is too large");
    }
    size_t allocation_size = count * element_size;
    size_t remainder = allocation_size % cache_line_size;
    if (remainder != 0) {
        size_t padding = cache_line_size - remainder;
        if (allocation_size > SIZE_MAX - padding) {
            fail_message("Action Execution allocation is too large");
        }
        allocation_size += padding;
    }
    return aligned_alloc(cache_line_size, allocation_size);
}

static double monotonic_seconds(void) {
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now) != 0) {
        perror("clock_gettime");
        exit(EXIT_FAILURE);
    }
    return (double)now.tv_sec + (double)now.tv_nsec / 1000000000.0;
}

static void pin_worker(size_t worker_index) {
#if defined(LITERAL_C_GEM5_ROI)
    (void)worker_index;
#else
    cpu_set_t allowed;
    CPU_ZERO(&allowed);
    if (sched_getaffinity(0, sizeof(allowed), &allowed) != 0) {
        perror("sched_getaffinity");
        exit(EXIT_FAILURE);
    }

    size_t selected = 0;
    for (size_t processor = 0; processor < (size_t)CPU_SETSIZE; ++processor) {
        if (!CPU_ISSET(processor, &allowed)) {
            continue;
        }
        if (selected == worker_index) {
            cpu_set_t target;
            CPU_ZERO(&target);
            CPU_SET(processor, &target);
            int error_number = pthread_setaffinity_np(
                pthread_self(), sizeof(target), &target
            );
            if (error_number != 0) {
                fail_errno("pthread_setaffinity_np", error_number);
            }
            return;
        }
        ++selected;
    }
    fail_message("not enough allowed processors for requested workers");
#endif
}

static uint64_t perform_work(uint64_t value, unsigned int work_amount) {
    for (unsigned int iteration = 0; iteration < work_amount; ++iteration) {
        value ^= value >> 12;
        value ^= value << 25;
        value ^= value >> 27;
        value *= UINT64_C(0x2545f4914f6cdd1d);
    }
    return value | UINT64_C(1);
}

static bool predecessor_contributes(size_t predecessor, size_t join_index) {
#if JOIN_FUSION_JOIN_COUNT == 1
    (void)join_index;
    return predecessor < join_fan_in;
#else
    size_t distance = (predecessor + predecessor_count - join_index)
        % predecessor_count;
    return distance < join_fan_in;
#endif
}

static void satisfy_join(
    ActionExecution *execution,
    size_t execution_index,
    size_t join_index,
    unsigned int work_amount
) {
    uint64_t seed = ((uint64_t)execution_index + UINT64_C(1))
        * UINT64_C(0x9e3779b97f4a7c15);
    execution->results[join_index] = perform_work(
        seed ^ ((uint64_t)join_index + UINT64_C(1)), work_amount
    );
}

#if JOIN_FUSION_BATCH_SATISFIED
static void dispatch_satisfied(
    ActionExecution *execution,
    size_t execution_index,
    uint64_t satisfied,
    unsigned int work_amount
) {
#if JOIN_FUSION_PUBLISH_READINESS
    atomic_fetch_or_explicit(
        &execution->ready_joins, satisfied, memory_order_release
    );
    satisfied = atomic_exchange_explicit(
        &execution->ready_joins, 0, memory_order_acq_rel
    );
#endif
    for (size_t join_index = 0; join_index < JOIN_FUSION_JOIN_COUNT; ++join_index) {
        if ((satisfied & (UINT64_C(1) << join_index)) != 0) {
            satisfy_join(execution, execution_index, join_index, work_amount);
        }
    }
}
#endif

#if JOIN_FUSION_REPRESENTATION == JOIN_FUSION_PACKED \
    || JOIN_FUSION_REPRESENTATION == JOIN_FUSION_PACKED_COMPACT
static uint64_t packed_initial_value(void) {
    uint64_t value = 0;
    for (size_t join_index = 0; join_index < JOIN_FUSION_JOIN_COUNT; ++join_index) {
        value |= (uint64_t)join_fan_in << (join_index * 8);
    }
    return value;
}

static uint64_t packed_arrival_value(size_t predecessor) {
    uint64_t value = 0;
    for (size_t join_index = 0; join_index < JOIN_FUSION_JOIN_COUNT; ++join_index) {
        if (predecessor_contributes(predecessor, join_index)) {
            value |= UINT64_C(1) << (join_index * 8);
        }
    }
    return value;
}
#endif

static void complete_predecessor(
    ActionExecution *execution,
    size_t execution_index,
    size_t predecessor,
    unsigned int work_amount
) {
#if JOIN_FUSION_BATCH_SATISFIED
    uint64_t satisfied = 0;
#endif
#if JOIN_FUSION_REPRESENTATION == JOIN_FUSION_PACKED \
    || JOIN_FUSION_REPRESENTATION == JOIN_FUSION_PACKED_COMPACT
    uint64_t arrival = packed_arrival_value(predecessor);
    if (arrival == 0) {
        return;
    }
    uint64_t previous = atomic_fetch_sub_explicit(
        &execution->packed_joins, arrival, memory_order_acq_rel
    );
    for (size_t join_index = 0; join_index < JOIN_FUSION_JOIN_COUNT; ++join_index) {
        uint64_t lane_mask = UINT64_C(0xff) << (join_index * 8);
        if ((arrival & lane_mask) != 0
            && (previous & lane_mask) == (UINT64_C(1) << (join_index * 8))) {
#if JOIN_FUSION_BATCH_SATISFIED
            satisfied |= UINT64_C(1) << join_index;
#else
            satisfy_join(execution, execution_index, join_index, work_amount);
#endif
        }
    }
#else
    for (size_t join_index = 0; join_index < JOIN_FUSION_JOIN_COUNT; ++join_index) {
        if (!predecessor_contributes(predecessor, join_index)) {
            continue;
        }
#if JOIN_FUSION_REPRESENTATION == JOIN_FUSION_FLAT_COMPACT
        unsigned int previous = atomic_fetch_sub_explicit(
            &execution->joins[join_index], 1, memory_order_acq_rel
        );
#else
        unsigned int previous = atomic_fetch_sub_explicit(
            &execution->joins[join_index].remaining, 1, memory_order_acq_rel
        );
#endif
        if (previous == 1) {
#if JOIN_FUSION_BATCH_SATISFIED
            satisfied |= UINT64_C(1) << join_index;
#else
            satisfy_join(execution, execution_index, join_index, work_amount);
#endif
        }
    }
#endif
#if JOIN_FUSION_BATCH_SATISFIED
    if (satisfied != 0) {
        dispatch_satisfied(
            execution, execution_index, satisfied, work_amount
        );
    }
#endif
}

static void *worker_main(void *argument) {
    Worker *worker = argument;
    Benchmark *benchmark = worker->benchmark;
    pin_worker(worker->worker_index);

    int error_number = pthread_barrier_wait(&benchmark->ready_barrier);
    if (error_number != 0 && error_number != PTHREAD_BARRIER_SERIAL_THREAD) {
        fail_errno("pthread_barrier_wait", error_number);
    }
    while (!atomic_load_explicit(&benchmark->start, memory_order_acquire)) {
        __asm__ volatile("" ::: "memory");
    }

    size_t task_count = benchmark->execution_count * predecessor_count;
    for (size_t task = worker->worker_index; task < task_count;
         task += benchmark->worker_count) {
        size_t execution_index = task / predecessor_count;
        size_t predecessor = task % predecessor_count;
        complete_predecessor(
            &benchmark->executions[execution_index],
            execution_index,
            predecessor,
            benchmark->work_amount
        );
    }
    return NULL;
}

static void initialize_execution(ActionExecution *execution) {
#if JOIN_FUSION_REPRESENTATION == JOIN_FUSION_FLAT_COMPACT
    for (size_t join_index = 0; join_index < JOIN_FUSION_JOIN_COUNT; ++join_index) {
        atomic_init(&execution->joins[join_index], join_fan_in);
    }
#elif JOIN_FUSION_REPRESENTATION == JOIN_FUSION_FLAT_ISOLATED
    for (size_t join_index = 0; join_index < JOIN_FUSION_JOIN_COUNT; ++join_index) {
        atomic_init(&execution->joins[join_index].remaining, join_fan_in);
    }
#else
    atomic_init(&execution->packed_joins, packed_initial_value());
#endif
#if JOIN_FUSION_PUBLISH_READINESS
    atomic_init(&execution->ready_joins, 0);
#endif
    for (size_t join_index = 0; join_index < JOIN_FUSION_JOIN_COUNT; ++join_index) {
        execution->results[join_index] = 0;
    }
}

static void verify(const Benchmark *benchmark) {
    for (size_t execution_index = 0; execution_index < benchmark->execution_count;
         ++execution_index) {
        const ActionExecution *execution = &benchmark->executions[execution_index];
        for (size_t join_index = 0; join_index < JOIN_FUSION_JOIN_COUNT;
             ++join_index) {
            if (execution->results[join_index] == 0) {
                fail_message("a Join successor did not execute");
            }
        }
    }
}

int main(int argc, char **argv) {
    if (argc != 4) {
        fprintf(stderr, "usage: %s EXECUTIONS WORKERS WORK_AMOUNT\n", argv[0]);
        return EXIT_FAILURE;
    }

    Benchmark benchmark = {
        .execution_count = parse_size(argv[1], "execution count"),
        .worker_count = parse_size(argv[2], "worker count"),
        .work_amount = parse_unsigned(argv[3], "work amount"),
    };
    if (benchmark.execution_count == 0) {
        fail_message("execution count must be positive");
    }
    if (benchmark.worker_count == 0 || benchmark.worker_count > maximum_workers) {
        fail_message("worker count must be between 1 and 32");
    }
    if (benchmark.execution_count > SIZE_MAX / predecessor_count) {
        fail_message("execution count is too large");
    }

    benchmark.executions = allocate_executions(
        benchmark.execution_count, sizeof(*benchmark.executions)
    );
    if (benchmark.executions == NULL) {
        perror("aligned_alloc");
        return EXIT_FAILURE;
    }
    for (size_t execution_index = 0; execution_index < benchmark.execution_count;
         ++execution_index) {
        initialize_execution(&benchmark.executions[execution_index]);
    }
    atomic_init(&benchmark.start, false);

    int error_number = pthread_barrier_init(
        &benchmark.ready_barrier, NULL, (unsigned int)benchmark.worker_count + 1
    );
    if (error_number != 0) {
        fail_errno("pthread_barrier_init", error_number);
    }

    pthread_t threads[maximum_workers] = {0};
    for (size_t worker_index = 0; worker_index < benchmark.worker_count;
         ++worker_index) {
        benchmark.workers[worker_index] = (Worker){
            .benchmark = &benchmark,
            .worker_index = worker_index,
        };
        error_number = pthread_create(
            &threads[worker_index],
            NULL,
            worker_main,
            &benchmark.workers[worker_index]
        );
        if (error_number != 0) {
            fail_errno("pthread_create", error_number);
        }
    }

    error_number = pthread_barrier_wait(&benchmark.ready_barrier);
    if (error_number != 0 && error_number != PTHREAD_BARRIER_SERIAL_THREAD) {
        fail_errno("pthread_barrier_wait", error_number);
    }
    double start = monotonic_seconds();
#if defined(LITERAL_C_GEM5_ROI)
    m5_work_begin(0, 0);
#endif
    atomic_store_explicit(&benchmark.start, true, memory_order_release);
    for (size_t worker_index = 0; worker_index < benchmark.worker_count;
         ++worker_index) {
        error_number = pthread_join(threads[worker_index], NULL);
        if (error_number != 0) {
            fail_errno("pthread_join", error_number);
        }
    }
#if defined(LITERAL_C_GEM5_ROI)
    m5_work_end(0, 0);
#endif
    double elapsed = monotonic_seconds() - start;

    verify(&benchmark);
    printf(
        "representation=%d joins=%d publish_readiness=%d batch_satisfied=%d "
        "executions=%zu workers=%zu work=%u "
        "elapsed_ns=%.0f ns_per_execution=%.3f ns_per_predecessor=%.3f\n",
        JOIN_FUSION_REPRESENTATION,
        JOIN_FUSION_JOIN_COUNT,
        JOIN_FUSION_PUBLISH_READINESS,
        JOIN_FUSION_BATCH_SATISFIED,
        benchmark.execution_count,
        benchmark.worker_count,
        benchmark.work_amount,
        elapsed * 1.0e9,
        elapsed * 1.0e9 / (double)benchmark.execution_count,
        elapsed * 1.0e9
            / ((double)benchmark.execution_count * (double)predecessor_count)
    );

    error_number = pthread_barrier_destroy(&benchmark.ready_barrier);
    if (error_number != 0) {
        fail_errno("pthread_barrier_destroy", error_number);
    }
    free(benchmark.executions);
    return EXIT_SUCCESS;
}
