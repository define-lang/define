#define main scheduler_example_main
#include "scheduler_and_join_example.c"
#undef main

#include <limits.h>
#include <time.h>

typedef enum {
    benchmark_serial,
    benchmark_wide,
    benchmark_steal,
    benchmark_skew,
    benchmark_wide_smt,
    benchmark_steal_smt,
    benchmark_skew_smt,
} BenchmarkWorkload;

typedef enum {
    benchmark_compute_work,
    benchmark_memory_work,
} BenchmarkWorkKind;

typedef enum {
    benchmark_uniform_cost,
    benchmark_interleaved_cost,
    benchmark_randomized_cost,
    benchmark_clustered_cost,
    benchmark_late_clustered_cost,
    benchmark_group_zero_cost,
    benchmark_group_one_cost,
} BenchmarkCostDistribution;

typedef struct {
    BenchmarkWorkload workload;
    BenchmarkWorkKind work_kind;
    BenchmarkCostDistribution cost_distribution;
    size_t task_count;
    unsigned int fast_work_amount;
    unsigned int slow_work_amount;
    size_t slow_task_count;
    size_t memory_bytes_per_task;
    size_t warmup_count;
    size_t sample_count;
} BenchmarkParameters;

typedef struct SchedulerBenchmark SchedulerBenchmark;

typedef struct {
    LiteralSchedulerTask task;
    SchedulerBenchmark *benchmark;
    size_t index;
    uint64_t value;
    uint64_t *memory;
    unsigned int work_amount;
} SchedulerBenchmarkTask;

struct SchedulerBenchmark {
    LiteralSchedulerTask start;
    SchedulerBenchmarkTask *tasks;
    uint64_t *memory;
    size_t task_count;
    size_t memory_words_per_task;
    BenchmarkWorkload workload;
    LiteralJoin join;
};

typedef struct {
    SchedulerBenchmark *benchmark;
    int processor_id;
    uint16_t group;
} BenchmarkMemoryInitializer;

static uint64_t run_benchmark_work(uint64_t value, unsigned int rounds) {
    for (unsigned int round = 0; round < rounds; ++round) {
        value ^= value << 13;
        value ^= value >> 7;
        value ^= value << 17;
    }
    return value;
}

static uint64_t run_benchmark_memory_work(SchedulerBenchmarkTask *task) {
    uint64_t value = task->value;
    for (unsigned int pass = 0; pass < task->work_amount; ++pass) {
        uint64_t increment = value + pass;
        for (size_t word = 0; word < task->benchmark->memory_words_per_task;
             ++word) {
            task->memory[word] += increment;
        }
        value ^= task->memory[
            (value + pass) % task->benchmark->memory_words_per_task
        ];
    }
    return value;
}

static void *initialize_benchmark_memory(void *opaque_initializer) {
    BenchmarkMemoryInitializer *initializer = opaque_initializer;
    SchedulerBenchmark *benchmark = initializer->benchmark;
    pin_current_thread(initializer->processor_id);
    for (size_t task_index = 0; task_index < benchmark->task_count;
         ++task_index) {
        SchedulerBenchmarkTask *task = &benchmark->tasks[task_index];
        if (task->task.preferred_group != initializer->group) {
            continue;
        }
        memset(
            task->memory,
            0,
            benchmark->memory_words_per_task * sizeof(*task->memory)
        );
    }
    return NULL;
}

static void first_touch_benchmark_memory(SchedulerBenchmark *benchmark) {
    size_t initializer_count = 1;
    BenchmarkMemoryInitializer initializers[2] = {
        {
            .benchmark = benchmark,
            .processor_id = 0,
            .group = 0,
        },
    };
    if (benchmark->workload == benchmark_wide
        || benchmark->workload == benchmark_wide_smt) {
        initializer_count = 2;
        initializers[1] = (BenchmarkMemoryInitializer){
            .benchmark = benchmark,
            .processor_id = 8,
            .group = 1,
        };
    }
    pthread_t threads[2];
    for (size_t initializer_index = 0;
         initializer_index < initializer_count;
         ++initializer_index) {
        int error_number = pthread_create(
            &threads[initializer_index],
            NULL,
            initialize_benchmark_memory,
            &initializers[initializer_index]
        );
        if (error_number != 0) {
            fail_errno("pthread_create", error_number);
        }
    }
    for (size_t initializer_index = 0;
         initializer_index < initializer_count;
         ++initializer_index) {
        int error_number = pthread_join(threads[initializer_index], NULL);
        if (error_number != 0) {
            fail_errno("pthread_join", error_number);
        }
    }
}

static void *allocate_uninitialized_aligned(size_t alignment, size_t size) {
    void *allocation = NULL;
    int error_number = posix_memalign(&allocation, alignment, size);
    if (error_number != 0) {
        fail_errno("posix_memalign", error_number);
    }
    return allocation;
}

static LiteralSchedulerTask *run_parallel_benchmark_task(
    LiteralSchedulerWorker *worker, LiteralSchedulerTask *task
) {
    SchedulerBenchmarkTask *benchmark_task = task->context;
    SchedulerBenchmark *benchmark = benchmark_task->benchmark;
    benchmark_task->value = run_benchmark_work(
        benchmark_task->value, benchmark_task->work_amount
    );
    if (literal_join_arrive(&benchmark->join)) {
        literal_scheduler_finish(worker);
    }
    return NULL;
}

static LiteralSchedulerTask *run_parallel_memory_benchmark_task(
    LiteralSchedulerWorker *worker, LiteralSchedulerTask *task
) {
    SchedulerBenchmarkTask *benchmark_task = task->context;
    SchedulerBenchmark *benchmark = benchmark_task->benchmark;
    benchmark_task->value = run_benchmark_memory_work(benchmark_task);
    if (literal_join_arrive(&benchmark->join)) {
        literal_scheduler_finish(worker);
    }
    return NULL;
}

static LiteralSchedulerTask *run_serial_benchmark_task(
    LiteralSchedulerWorker *worker, LiteralSchedulerTask *task
) {
    SchedulerBenchmarkTask *benchmark_task = task->context;
    SchedulerBenchmark *benchmark = benchmark_task->benchmark;
    benchmark_task->value = run_benchmark_work(
        benchmark_task->value, benchmark_task->work_amount
    );
    size_t next_index = benchmark_task->index + 1;
    if (next_index == benchmark->task_count) {
        literal_scheduler_finish(worker);
        return NULL;
    }
    return &benchmark->tasks[next_index].task;
}

static LiteralSchedulerTask *run_serial_memory_benchmark_task(
    LiteralSchedulerWorker *worker, LiteralSchedulerTask *task
) {
    SchedulerBenchmarkTask *benchmark_task = task->context;
    SchedulerBenchmark *benchmark = benchmark_task->benchmark;
    benchmark_task->value = run_benchmark_memory_work(benchmark_task);
    size_t next_index = benchmark_task->index + 1;
    if (next_index == benchmark->task_count) {
        literal_scheduler_finish(worker);
        return NULL;
    }
    return &benchmark->tasks[next_index].task;
}

static LiteralSchedulerTask *run_benchmark_start(
    LiteralSchedulerWorker *worker, LiteralSchedulerTask *task
) {
    SchedulerBenchmark *benchmark = task->context;
    if (benchmark->workload == benchmark_serial) {
        return &benchmark->tasks[0].task;
    }
    for (size_t task_index = 0; task_index < benchmark->task_count;
         ++task_index) {
        literal_scheduler_submit(worker, &benchmark->tasks[task_index].task);
    }
    return NULL;
}

static uint64_t monotonic_nanoseconds(void) {
    struct timespec time;
    if (clock_gettime(CLOCK_MONOTONIC_RAW, &time) != 0) {
        fail_message("clock_gettime failed");
    }
    return (uint64_t)time.tv_sec * UINT64_C(1000000000)
        + (uint64_t)time.tv_nsec;
}

static void configure_scheduler(
    LiteralSchedulerConfig *config, BenchmarkWorkload workload
) {
    memset(config, 0, sizeof(*config));
    config->cross_group_poll_delay = 64;
    if (workload == benchmark_serial) {
        config->worker_count = 1;
        config->group_count = 1;
        config->processor_ids[0] = 0;
        return;
    }
    if (workload == benchmark_steal) {
        config->worker_count = 8;
        config->group_count = 1;
        for (size_t worker_index = 0; worker_index < config->worker_count;
             ++worker_index) {
            config->processor_ids[worker_index] = (int)worker_index;
        }
        return;
    }
    if (workload == benchmark_steal_smt) {
        config->worker_count = 16;
        config->group_count = 1;
        for (size_t worker_index = 0; worker_index < 8; ++worker_index) {
            config->processor_ids[worker_index] = (int)worker_index;
            config->processor_ids[worker_index + 8] = (int)worker_index + 16;
        }
        return;
    }
    if (workload == benchmark_wide_smt || workload == benchmark_skew_smt) {
        config->worker_count = 4;
        config->group_count = 2;
        config->processor_ids[0] = 0;
        config->processor_ids[1] = 16;
        config->processor_ids[2] = 8;
        config->processor_ids[3] = 24;
        config->group_ids[2] = 1;
        config->group_ids[3] = 1;
        return;
    }
    config->worker_count = 2;
    config->group_count = 2;
    config->processor_ids[0] = 0;
    config->processor_ids[1] = 8;
    config->group_ids[1] = 1;
}

static uint16_t preferred_group(
    BenchmarkWorkload workload, size_t task_index
) {
    if (workload == benchmark_wide || workload == benchmark_wide_smt) {
        return (uint16_t)(task_index & 1);
    }
    return 0;
}

static uint64_t next_shuffle_random(uint64_t *state) {
    *state ^= *state << 13;
    *state ^= *state >> 7;
    *state ^= *state << 17;
    return *state;
}

static void assign_slow_work(
    SchedulerBenchmark *benchmark, const BenchmarkParameters *parameters
) {
    if (parameters->slow_task_count == 0) {
        return;
    }
    if (parameters->cost_distribution == benchmark_clustered_cost) {
        for (size_t task_index = 0;
             task_index < parameters->slow_task_count;
             ++task_index) {
            benchmark->tasks[task_index].work_amount =
                parameters->slow_work_amount;
        }
        return;
    }
    if (parameters->cost_distribution == benchmark_late_clustered_cost) {
        size_t first_slow_task = parameters->task_count
            - parameters->slow_task_count;
        for (size_t task_index = first_slow_task;
             task_index < parameters->task_count;
             ++task_index) {
            benchmark->tasks[task_index].work_amount =
                parameters->slow_work_amount;
        }
        return;
    }
    if (parameters->cost_distribution == benchmark_interleaved_cost) {
        size_t accumulator = 0;
        for (size_t task_index = 0; task_index < parameters->task_count;
             ++task_index) {
            accumulator += parameters->slow_task_count;
            if (accumulator >= parameters->task_count) {
                benchmark->tasks[task_index].work_amount =
                    parameters->slow_work_amount;
                accumulator -= parameters->task_count;
            }
        }
        return;
    }
    if (parameters->cost_distribution == benchmark_randomized_cost) {
        for (size_t task_index = 0;
             task_index < parameters->slow_task_count;
             ++task_index) {
            benchmark->tasks[task_index].work_amount =
                parameters->slow_work_amount;
        }
        uint64_t random_state = UINT64_C(0xd1b54a32d192ed03);
        for (size_t remaining = parameters->task_count; remaining > 1;
             --remaining) {
            size_t swap_index = (size_t)(
                next_shuffle_random(&random_state) % remaining
            );
            unsigned int work_amount =
                benchmark->tasks[remaining - 1].work_amount;
            benchmark->tasks[remaining - 1].work_amount =
                benchmark->tasks[swap_index].work_amount;
            benchmark->tasks[swap_index].work_amount = work_amount;
        }
        return;
    }
    uint16_t slow_group = 0;
    if (parameters->cost_distribution == benchmark_group_one_cost) {
        slow_group = 1;
    }
    size_t assigned_count = 0;
    for (size_t task_index = 0; task_index < parameters->task_count;
         ++task_index) {
        if (benchmark->tasks[task_index].task.preferred_group != slow_group) {
            continue;
        }
        benchmark->tasks[task_index].work_amount = parameters->slow_work_amount;
        ++assigned_count;
        if (assigned_count == parameters->slow_task_count) {
            return;
        }
    }
    fail_message("not enough tasks in the selected slow topology group");
}

static uint64_t run_benchmark_sample(
    const BenchmarkParameters *parameters,
    uint64_t *checksum
) {
    SchedulerBenchmark benchmark = {
        .start = {
            .function = run_benchmark_start,
            .preferred_group = 0,
        },
        .task_count = parameters->task_count,
        .workload = parameters->workload,
    };
    benchmark.start.context = &benchmark;
    if (parameters->workload != benchmark_serial) {
        literal_join_initialize(
            &benchmark.join, (unsigned int)parameters->task_count
        );
    }
    benchmark.tasks = calloc(parameters->task_count, sizeof(*benchmark.tasks));
    if (benchmark.tasks == NULL) {
        fail_message("benchmark task allocation failed");
    }
    if (parameters->work_kind == benchmark_memory_work) {
        benchmark.memory_words_per_task =
            parameters->memory_bytes_per_task / sizeof(*benchmark.memory);
        benchmark.memory = allocate_uninitialized_aligned(
            example_cache_line_alignment,
            parameters->task_count * parameters->memory_bytes_per_task
        );
    }
    LiteralSchedulerTaskFunction task_function = run_parallel_benchmark_task;
    if (parameters->work_kind == benchmark_memory_work) {
        task_function = run_parallel_memory_benchmark_task;
    }
    if (parameters->workload == benchmark_serial) {
        task_function = run_serial_benchmark_task;
        if (parameters->work_kind == benchmark_memory_work) {
            task_function = run_serial_memory_benchmark_task;
        }
    }
    for (size_t task_index = 0; task_index < parameters->task_count;
         ++task_index) {
        SchedulerBenchmarkTask *benchmark_task = &benchmark.tasks[task_index];
        benchmark_task->benchmark = &benchmark;
        benchmark_task->index = task_index;
        benchmark_task->value = task_index + UINT64_C(0x9e3779b97f4a7c15);
        benchmark_task->work_amount = parameters->fast_work_amount;
        if (benchmark.memory != NULL) {
            benchmark_task->memory = benchmark.memory
                + task_index * benchmark.memory_words_per_task;
        }
        benchmark_task->task = (LiteralSchedulerTask){
            .function = task_function,
            .context = benchmark_task,
            .preferred_group = preferred_group(
                parameters->workload, task_index
            ),
        };
    }
    assign_slow_work(&benchmark, parameters);
    if (benchmark.memory != NULL) {
        first_touch_benchmark_memory(&benchmark);
    }

    LiteralSchedulerConfig config;
    configure_scheduler(&config, parameters->workload);
    LiteralScheduler scheduler;
    uint64_t start = monotonic_nanoseconds();
    literal_scheduler_initialize(&scheduler, &config);
    literal_scheduler_run(&scheduler, &benchmark.start);
    literal_scheduler_destroy(&scheduler);
    uint64_t elapsed = monotonic_nanoseconds() - start;

    uint64_t sample_checksum = 0;
    for (size_t task_index = 0; task_index < parameters->task_count;
         ++task_index) {
        sample_checksum = (
            sample_checksum ^ benchmark.tasks[task_index].value
        ) * UINT64_C(0x100000001b3);
    }
    size_t memory_word_count = parameters->task_count
        * benchmark.memory_words_per_task;
    for (size_t word = 0; word < memory_word_count; ++word) {
        sample_checksum = (sample_checksum ^ benchmark.memory[word])
            * UINT64_C(0x100000001b3);
    }
    *checksum += sample_checksum;
    free(benchmark.memory);
    free(benchmark.tasks);
    return elapsed;
}

static int compare_uint64(const void *left, const void *right) {
    uint64_t left_value = *(const uint64_t *)left;
    uint64_t right_value = *(const uint64_t *)right;
    return (left_value > right_value) - (left_value < right_value);
}

static BenchmarkWorkload parse_workload(const char *name) {
    if (strcmp(name, "serial") == 0) {
        return benchmark_serial;
    }
    if (strcmp(name, "wide") == 0) {
        return benchmark_wide;
    }
    if (strcmp(name, "steal") == 0) {
        return benchmark_steal;
    }
    if (strcmp(name, "skew") == 0) {
        return benchmark_skew;
    }
    if (strcmp(name, "wide-smt") == 0) {
        return benchmark_wide_smt;
    }
    if (strcmp(name, "steal-smt") == 0) {
        return benchmark_steal_smt;
    }
    if (strcmp(name, "skew-smt") == 0) {
        return benchmark_skew_smt;
    }
    fail_message("unknown benchmark workload");
    return benchmark_serial;
}

static BenchmarkWorkKind parse_work_kind(const char *name) {
    if (strcmp(name, "compute") == 0) {
        return benchmark_compute_work;
    }
    if (strcmp(name, "memory") == 0) {
        return benchmark_memory_work;
    }
    fail_message("unknown benchmark work kind");
    return benchmark_compute_work;
}

static BenchmarkCostDistribution parse_cost_distribution(const char *name) {
    if (strcmp(name, "uniform") == 0) {
        return benchmark_uniform_cost;
    }
    if (strcmp(name, "interleaved") == 0) {
        return benchmark_interleaved_cost;
    }
    if (strcmp(name, "random") == 0) {
        return benchmark_randomized_cost;
    }
    if (strcmp(name, "clustered") == 0) {
        return benchmark_clustered_cost;
    }
    if (strcmp(name, "late") == 0) {
        return benchmark_late_clustered_cost;
    }
    if (strcmp(name, "group0") == 0) {
        return benchmark_group_zero_cost;
    }
    if (strcmp(name, "group1") == 0) {
        return benchmark_group_one_cost;
    }
    fail_message("unknown benchmark cost distribution");
    return benchmark_uniform_cost;
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

static void validate_parameters(const BenchmarkParameters *parameters) {
    if (parameters->task_count == 0 || parameters->sample_count == 0) {
        fail_message("benchmark tasks and samples must be nonzero");
    }
    if (parameters->workload != benchmark_serial
        && parameters->task_count > example_queue_capacity) {
        fail_message("parallel benchmark task count exceeds queue capacity");
    }
    if (parameters->slow_task_count > parameters->task_count) {
        fail_message("slow task count exceeds total task count");
    }
    if (parameters->cost_distribution == benchmark_uniform_cost
        && parameters->slow_task_count != 0) {
        fail_message("uniform cost requires zero slow tasks");
    }
    if (parameters->cost_distribution != benchmark_uniform_cost
        && parameters->slow_task_count == 0) {
        fail_message("a mixed cost distribution requires slow tasks");
    }
    if (parameters->slow_work_amount < parameters->fast_work_amount) {
        fail_message("slow work must not be less than fast work");
    }
    if (parameters->cost_distribution == benchmark_group_one_cost
        && parameters->workload != benchmark_wide
        && parameters->workload != benchmark_wide_smt) {
        fail_message("group1 cost requires the wide workload");
    }
    if (parameters->work_kind == benchmark_compute_work) {
        if (parameters->memory_bytes_per_task != 0) {
            fail_message("compute work requires zero memory bytes per task");
        }
        return;
    }
    if (parameters->memory_bytes_per_task < sizeof(uint64_t)
        || parameters->memory_bytes_per_task % sizeof(uint64_t) != 0) {
        fail_message("memory bytes per task must be a nonzero uint64 multiple");
    }
    if (parameters->task_count
        > SIZE_MAX / parameters->memory_bytes_per_task) {
        fail_message("benchmark memory allocation size overflows size_t");
    }
}

int main(int argument_count, char **arguments) {
    if (argument_count != 11) {
        fail_message(
            "usage: benchmark workload tasks work-kind fast-work slow-work "
            "slow-tasks distribution memory-bytes warmups samples"
        );
    }
    BenchmarkParameters parameters = {
        .workload = parse_workload(arguments[1]),
        .work_kind = parse_work_kind(arguments[3]),
        .cost_distribution = parse_cost_distribution(arguments[7]),
    };
    unsigned long parsed_task_count = parse_unsigned_argument(
        arguments[2], "tasks"
    );
    unsigned long parsed_fast_work_amount = parse_unsigned_argument(
        arguments[4], "fast-work"
    );
    unsigned long parsed_slow_work_amount = parse_unsigned_argument(
        arguments[5], "slow-work"
    );
    unsigned long parsed_slow_task_count = parse_unsigned_argument(
        arguments[6], "slow-tasks"
    );
    unsigned long parsed_memory_bytes_per_task = parse_unsigned_argument(
        arguments[8], "memory-bytes"
    );
    unsigned long parsed_warmup_count = parse_unsigned_argument(
        arguments[9], "warmups"
    );
    unsigned long parsed_sample_count = parse_unsigned_argument(
        arguments[10], "samples"
    );
    if (parsed_task_count > SIZE_MAX || parsed_fast_work_amount > UINT_MAX
        || parsed_slow_work_amount > UINT_MAX
        || parsed_slow_task_count > SIZE_MAX
        || parsed_memory_bytes_per_task > SIZE_MAX
        || parsed_warmup_count > SIZE_MAX || parsed_sample_count > SIZE_MAX) {
        fail_message("benchmark argument exceeds its supported range");
    }
    parameters.task_count = (size_t)parsed_task_count;
    parameters.fast_work_amount = (unsigned int)parsed_fast_work_amount;
    parameters.slow_work_amount = (unsigned int)parsed_slow_work_amount;
    parameters.slow_task_count = (size_t)parsed_slow_task_count;
    parameters.memory_bytes_per_task =
        (size_t)parsed_memory_bytes_per_task;
    parameters.warmup_count = (size_t)parsed_warmup_count;
    parameters.sample_count = (size_t)parsed_sample_count;
    validate_parameters(&parameters);
    uint64_t checksum = 0;
    for (size_t warmup = 0; warmup < parameters.warmup_count; ++warmup) {
        (void)run_benchmark_sample(&parameters, &checksum);
    }
    uint64_t *samples = calloc(parameters.sample_count, sizeof(*samples));
    if (samples == NULL) {
        fail_message("benchmark sample allocation failed");
    }
    for (size_t sample = 0; sample < parameters.sample_count; ++sample) {
        samples[sample] = run_benchmark_sample(&parameters, &checksum);
    }
    qsort(samples, parameters.sample_count, sizeof(*samples), compare_uint64);
    size_t p90_index = (parameters.sample_count / 10) * 9
        + ((parameters.sample_count % 10) * 9) / 10;
    if (p90_index == parameters.sample_count) {
        p90_index = parameters.sample_count - 1;
    }
    printf(
        "min_ns=%lu median_ns=%lu p90_ns=%lu ns_per_task=%.3f checksum=%lu\n",
        (unsigned long)samples[0],
        (unsigned long)samples[parameters.sample_count / 2],
        (unsigned long)samples[p90_index],
        (double)samples[parameters.sample_count / 2]
            / (double)parameters.task_count,
        (unsigned long)checksum
    );
    free(samples);
    return EXIT_SUCCESS;
}
