#define _GNU_SOURCE

#if !defined(__linux__)
#error "region_scheduler_benchmark.c requires Linux target runtime facilities"
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

#define REGION_SCHEDULER_EXECUTION_SHARDED 1
#define REGION_SCHEDULER_STATIC_BRANCHES 2
#define REGION_SCHEDULER_DYNAMIC_BRANCHES 3
#define REGION_SCHEDULER_HYBRID 4

#define REGION_TASK_ORDER_EXECUTION_MAJOR 1
#define REGION_TASK_ORDER_BRANCH_MAJOR 2

#if !defined(REGION_SCHEDULER)
#error "define REGION_SCHEDULER to one of the REGION_SCHEDULER_* values"
#endif

#if !defined(REGION_TASK_ORDER)
#define REGION_TASK_ORDER REGION_TASK_ORDER_EXECUTION_MAJOR
#endif

#if !defined(REGION_BRANCH_COUNT)
#define REGION_BRANCH_COUNT 4096
#endif

#if !defined(REGION_UNCERTAIN_STRIDE)
#define REGION_UNCERTAIN_STRIDE 8
#endif

#if !defined(REGION_CLAIM_SIZE)
#define REGION_CLAIM_SIZE 1
#endif

#if REGION_SCHEDULER < REGION_SCHEDULER_EXECUTION_SHARDED \
    || REGION_SCHEDULER > REGION_SCHEDULER_HYBRID
#error "invalid REGION_SCHEDULER"
#endif

#if REGION_TASK_ORDER < REGION_TASK_ORDER_EXECUTION_MAJOR \
    || REGION_TASK_ORDER > REGION_TASK_ORDER_BRANCH_MAJOR
#error "invalid REGION_TASK_ORDER"
#endif

#if REGION_BRANCH_COUNT < 1
#error "REGION_BRANCH_COUNT must be positive"
#endif

#if REGION_UNCERTAIN_STRIDE < 2
#error "REGION_UNCERTAIN_STRIDE must be at least two"
#endif

#if REGION_CLAIM_SIZE < 1 || REGION_CLAIM_SIZE > 64
#error "REGION_CLAIM_SIZE must be between one and 64"
#endif

enum {
    cache_line_size = 64,
    maximum_workers = 32,
    serial_operation_count = 32,
    branch_operation_count = 8,
};

typedef struct {
    alignas(cache_line_size) atomic_size_t remaining_arrivals;
    uint64_t prefix_value;
    uint64_t suffix_value;
} ActionExecution;

typedef struct Benchmark Benchmark;

typedef struct {
    Benchmark *benchmark;
    size_t worker_index;
} Worker;

struct Benchmark {
    ActionExecution *executions;
    uint64_t *branch_results;
    size_t execution_count;
    size_t worker_count;
    unsigned int fixed_work_amount;
    unsigned int variable_work_amount;
    uint64_t runtime_seed;
    atomic_size_t next_task;
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

static uint64_t mix(uint64_t value) {
    value ^= value >> 30;
    value *= UINT64_C(0xbf58476d1ce4e5b9);
    value ^= value >> 27;
    value *= UINT64_C(0x94d049bb133111eb);
    return value ^ (value >> 31);
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

static size_t uncertain_branch_count(void) {
    return (REGION_BRANCH_COUNT + REGION_UNCERTAIN_STRIDE - 1)
        / REGION_UNCERTAIN_STRIDE;
}

static bool branch_is_uncertain(size_t branch_index) {
    return branch_index % REGION_UNCERTAIN_STRIDE == 0;
}

static unsigned int branch_work_amount(
    const Benchmark *benchmark,
    size_t execution_index,
    size_t branch_index
) {
    if (!branch_is_uncertain(branch_index)) {
        return benchmark->fixed_work_amount;
    }
    uint64_t identity = (uint64_t)execution_index * REGION_BRANCH_COUNT
        + branch_index;
    bool takes_variable_path = (mix(identity ^ benchmark->runtime_seed) & 1) != 0;
    return takes_variable_path ? benchmark->variable_work_amount
                               : benchmark->fixed_work_amount;
}

static void execute_prefix(ActionExecution *execution, size_t execution_index) {
    uint64_t value = (uint64_t)execution_index + UINT64_C(1);
    for (size_t operation = 0; operation < serial_operation_count; ++operation) {
        value = mix(value + operation);
    }
    execution->prefix_value = value | UINT64_C(1);
}

static void execute_branch(
    Benchmark *benchmark, size_t execution_index, size_t branch_index
) {
    ActionExecution *execution = &benchmark->executions[execution_index];
    uint64_t value = execution->prefix_value ^ (uint64_t)(branch_index + 1);

    for (size_t operation = 0; operation < branch_operation_count; ++operation) {
        value = mix(value + operation);
    }
    value = perform_work(
        value,
        branch_work_amount(benchmark, execution_index, branch_index)
    );
    benchmark->branch_results[
        execution_index * REGION_BRANCH_COUNT + branch_index
    ] = value;
}

static void execute_suffix(
    Benchmark *benchmark, size_t execution_index, uint64_t arrival_value
) {
    ActionExecution *execution = &benchmark->executions[execution_index];
    uint64_t value = mix(execution->prefix_value ^ arrival_value);
    for (size_t operation = 0; operation < serial_operation_count; ++operation) {
        value = mix(value + operation);
    }
    execution->suffix_value = value | UINT64_C(1);
}

static void arrive(
    Benchmark *benchmark, size_t execution_index, uint64_t arrival_value
) {
    ActionExecution *execution = &benchmark->executions[execution_index];
    size_t previous = atomic_fetch_sub_explicit(
        &execution->remaining_arrivals, 1, memory_order_acq_rel
    );
    if (previous == 1) {
        execute_suffix(benchmark, execution_index, arrival_value);
    }
}

[[maybe_unused]] static void execute_sharded(Worker *worker) {
    Benchmark *benchmark = worker->benchmark;
    for (size_t execution_index = worker->worker_index;
         execution_index < benchmark->execution_count;
         execution_index += benchmark->worker_count) {
        for (size_t branch_index = 0; branch_index < REGION_BRANCH_COUNT;
             ++branch_index) {
            execute_branch(benchmark, execution_index, branch_index);
        }
        execute_suffix(benchmark, execution_index, UINT64_C(0x51a4ded));
    }
}

[[maybe_unused]] static void execute_static_branches(
    Worker *worker, bool omit_uncertain
) {
    Benchmark *benchmark = worker->benchmark;
    size_t first_branch = REGION_BRANCH_COUNT * worker->worker_index
        / benchmark->worker_count;
    size_t end_branch = REGION_BRANCH_COUNT * (worker->worker_index + 1)
        / benchmark->worker_count;

    for (size_t execution_index = 0;
         execution_index < benchmark->execution_count;
         ++execution_index) {
        for (size_t branch_index = first_branch; branch_index < end_branch;
             ++branch_index) {
            if (omit_uncertain && branch_is_uncertain(branch_index)) {
                continue;
            }
            execute_branch(benchmark, execution_index, branch_index);
        }
        arrive(benchmark, execution_index, worker->worker_index + UINT64_C(1));
    }
}

static void task_identity(
    const Benchmark *benchmark,
    size_t task,
    bool uncertain_only,
    size_t *execution_index,
    size_t *branch_index
) {
#if REGION_TASK_ORDER == REGION_TASK_ORDER_EXECUTION_MAJOR
    size_t branches_per_execution = uncertain_only ? uncertain_branch_count()
                                                   : REGION_BRANCH_COUNT;
    (void)benchmark;
    *execution_index = task / branches_per_execution;
    size_t branch_task = task % branches_per_execution;
#else
    size_t branch_task = task / benchmark->execution_count;
    *execution_index = task % benchmark->execution_count;
#endif
    *branch_index = uncertain_only ? branch_task * REGION_UNCERTAIN_STRIDE
                                   : branch_task;
}

[[maybe_unused]] static void execute_dynamic_branches(
    Worker *worker, bool uncertain_only
) {
    Benchmark *benchmark = worker->benchmark;
    size_t branches_per_execution = uncertain_only ? uncertain_branch_count()
                                                   : REGION_BRANCH_COUNT;
    size_t task_count = benchmark->execution_count * branches_per_execution;

    for (;;) {
        size_t first_task = atomic_fetch_add_explicit(
            &benchmark->next_task, REGION_CLAIM_SIZE, memory_order_relaxed
        );
        if (first_task >= task_count) {
            return;
        }
        size_t end_task = first_task + REGION_CLAIM_SIZE;
        if (end_task > task_count) {
            end_task = task_count;
        }
        for (size_t task = first_task; task < end_task; ++task) {
            size_t execution_index;
            size_t branch_index;
            task_identity(
                benchmark,
                task,
                uncertain_only,
                &execution_index,
                &branch_index
            );
            execute_branch(benchmark, execution_index, branch_index);
            arrive(benchmark, execution_index, branch_index + UINT64_C(1));
        }
    }
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

#if REGION_SCHEDULER == REGION_SCHEDULER_EXECUTION_SHARDED
    execute_sharded(worker);
#elif REGION_SCHEDULER == REGION_SCHEDULER_STATIC_BRANCHES
    execute_static_branches(worker, false);
#elif REGION_SCHEDULER == REGION_SCHEDULER_DYNAMIC_BRANCHES
    execute_dynamic_branches(worker, false);
#else
    execute_dynamic_branches(worker, true);
    execute_static_branches(worker, true);
#endif
    return NULL;
}

static void initialize(Benchmark *benchmark) {
    size_t initial_arrivals;
#if REGION_SCHEDULER == REGION_SCHEDULER_EXECUTION_SHARDED
    initial_arrivals = 0;
#elif REGION_SCHEDULER == REGION_SCHEDULER_STATIC_BRANCHES
    initial_arrivals = benchmark->worker_count;
#elif REGION_SCHEDULER == REGION_SCHEDULER_DYNAMIC_BRANCHES
    initial_arrivals = REGION_BRANCH_COUNT;
#else
    initial_arrivals = benchmark->worker_count + uncertain_branch_count();
#endif

    for (size_t execution_index = 0;
         execution_index < benchmark->execution_count;
         ++execution_index) {
        ActionExecution *execution = &benchmark->executions[execution_index];
        atomic_init(&execution->remaining_arrivals, initial_arrivals);
        execute_prefix(execution, execution_index);
        execution->suffix_value = 0;
    }
    size_t result_count = benchmark->execution_count * REGION_BRANCH_COUNT;
    for (size_t result_index = 0; result_index < result_count; ++result_index) {
        benchmark->branch_results[result_index] = 0;
    }
    atomic_init(&benchmark->next_task, 0);
    atomic_init(&benchmark->start, false);
}

static void verify(const Benchmark *benchmark) {
    for (size_t execution_index = 0;
         execution_index < benchmark->execution_count;
         ++execution_index) {
        const ActionExecution *execution = &benchmark->executions[execution_index];
        if (execution->prefix_value == 0 || execution->suffix_value == 0) {
            fail_message("an Action Execution did not complete");
        }
        for (size_t branch_index = 0; branch_index < REGION_BRANCH_COUNT;
             ++branch_index) {
            if (benchmark->branch_results[
                    execution_index * REGION_BRANCH_COUNT + branch_index
                ]
                == 0) {
                fail_message("a branch region did not complete");
            }
        }
    }
}

int main(int argc, char **argv) {
    if (argc != 6) {
        fprintf(
            stderr,
            "usage: %s EXECUTIONS WORKERS FIXED_WORK VARIABLE_WORK RUNTIME_SEED\n",
            argv[0]
        );
        return EXIT_FAILURE;
    }

    Benchmark benchmark = {
        .execution_count = parse_size(argv[1], "execution count"),
        .worker_count = parse_size(argv[2], "worker count"),
        .fixed_work_amount = parse_unsigned(argv[3], "fixed work amount"),
        .variable_work_amount = parse_unsigned(argv[4], "variable work amount"),
        .runtime_seed = parse_size(argv[5], "runtime seed"),
    };
    if (benchmark.execution_count == 0) {
        fail_message("execution count must be positive");
    }
    if (benchmark.worker_count == 0 || benchmark.worker_count > maximum_workers) {
        fail_message("worker count must be between 1 and 32");
    }
    if (benchmark.execution_count > SIZE_MAX / REGION_BRANCH_COUNT) {
        fail_message("execution count is too large");
    }
    size_t operations_per_execution = (size_t)2 * serial_operation_count
        + (size_t)REGION_BRANCH_COUNT * branch_operation_count;
    if (benchmark.execution_count > SIZE_MAX / operations_per_execution) {
        fail_message("execution count is too large");
    }

    benchmark.executions = allocate_executions(
        benchmark.execution_count, sizeof(*benchmark.executions)
    );
    benchmark.branch_results = calloc(
        benchmark.execution_count * REGION_BRANCH_COUNT,
        sizeof(*benchmark.branch_results)
    );
    if (benchmark.executions == NULL || benchmark.branch_results == NULL) {
        perror("allocate benchmark state");
        free(benchmark.branch_results);
        free(benchmark.executions);
        return EXIT_FAILURE;
    }
    initialize(&benchmark);

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
    size_t operation_count = benchmark.execution_count * operations_per_execution;
    printf(
        "scheduler=%d order=%d branches=%d claim=%d executions=%zu workers=%zu "
        "fixed_work=%u variable_work=%u elapsed_ns=%.0f "
        "ns_per_execution=%.3f ns_per_operation=%.3f\n",
        REGION_SCHEDULER,
        REGION_TASK_ORDER,
        REGION_BRANCH_COUNT,
        REGION_CLAIM_SIZE,
        benchmark.execution_count,
        benchmark.worker_count,
        benchmark.fixed_work_amount,
        benchmark.variable_work_amount,
        elapsed * 1.0e9,
        elapsed * 1.0e9 / (double)benchmark.execution_count,
        elapsed * 1.0e9 / (double)operation_count
    );

    error_number = pthread_barrier_destroy(&benchmark.ready_barrier);
    if (error_number != 0) {
        fail_errno("pthread_barrier_destroy", error_number);
    }
    free(benchmark.branch_results);
    free(benchmark.executions);
    return EXIT_SUCCESS;
}
