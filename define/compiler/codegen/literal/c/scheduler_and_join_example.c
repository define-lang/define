#define _GNU_SOURCE

#if !defined(__linux__)
#error "scheduler_and_join_example.c requires Linux target runtime facilities"
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
#include <string.h>

#if defined(__x86_64__) || defined(__i386__)
#include <immintrin.h>
#endif

enum {
    example_cache_line_alignment = 64,
    example_maximum_topology_groups = 2,
    example_maximum_workers = 32,
    example_queue_capacity = 65536,
};

_Static_assert(
    (example_queue_capacity & (example_queue_capacity - 1)) == 0,
    "the benchmark queue capacity must be a power of two"
);

typedef struct LiteralScheduler LiteralScheduler;
typedef struct LiteralSchedulerTask LiteralSchedulerTask;
typedef struct LiteralSchedulerWorker LiteralSchedulerWorker;

typedef LiteralSchedulerTask *(*LiteralSchedulerTaskFunction)(
    LiteralSchedulerWorker *, LiteralSchedulerTask *
);

struct LiteralSchedulerTask {
    LiteralSchedulerTaskFunction function;
    void *context;
    uint16_t preferred_group;
};

typedef struct {
    atomic_size_t sequence;
    LiteralSchedulerTask *task;
} QueueCell;

typedef struct {
    alignas(example_cache_line_alignment) atomic_size_t enqueue_position;
    unsigned char enqueue_padding[
        example_cache_line_alignment - sizeof(atomic_size_t)
    ];
    alignas(example_cache_line_alignment) atomic_size_t dequeue_position;
    unsigned char dequeue_padding[
        example_cache_line_alignment - sizeof(atomic_size_t)
    ];
    QueueCell *cells;
    size_t mask;
} MpmcQueue;

typedef struct {
    alignas(example_cache_line_alignment) atomic_int_fast64_t top;
    unsigned char top_padding[
        example_cache_line_alignment - sizeof(atomic_int_fast64_t)
    ];
    alignas(example_cache_line_alignment) atomic_int_fast64_t bottom;
    unsigned char bottom_padding[
        example_cache_line_alignment - sizeof(atomic_int_fast64_t)
    ];
    _Atomic(LiteralSchedulerTask *) *tasks;
    int64_t mask;
} WorkDeque;

typedef struct {
    alignas(example_cache_line_alignment) atomic_bool value;
    unsigned char padding[example_cache_line_alignment - sizeof(atomic_bool)];
} PaddedBoolean;

typedef struct {
    alignas(example_cache_line_alignment) atomic_uint remaining;
    unsigned char padding[example_cache_line_alignment - sizeof(atomic_uint)];
} LiteralJoin;

typedef struct {
    size_t worker_count;
    size_t group_count;
    int processor_ids[example_maximum_workers];
    uint16_t group_ids[example_maximum_workers];
    unsigned int cross_group_poll_delay;
} LiteralSchedulerConfig;

struct LiteralSchedulerWorker {
    WorkDeque deque;
    LiteralScheduler *scheduler;
    size_t index;
    uint64_t random_state;
    int processor_id;
    unsigned int failed_local_polls;
    uint16_t group;
};

struct LiteralScheduler {
    size_t worker_count;
    size_t group_count;
    LiteralSchedulerWorker workers[example_maximum_workers];
    MpmcQueue group_injection[example_maximum_topology_groups];
    pthread_barrier_t start_barrier;
    PaddedBoolean done;
    unsigned int cross_group_poll_delay;
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

static void require_lock_free_scheduler_atomics(void) {
    atomic_bool completion_state;
    atomic_uint join_counter;
    atomic_size_t queue_position;
    atomic_int_fast64_t deque_position;
    _Atomic(LiteralSchedulerTask *) task_pointer;
    atomic_init(&completion_state, false);
    atomic_init(&join_counter, 0);
    atomic_init(&queue_position, 0);
    atomic_init(&deque_position, 0);
    atomic_init(&task_pointer, NULL);
    if (!atomic_is_lock_free(&completion_state)
        || !atomic_is_lock_free(&join_counter)
        || !atomic_is_lock_free(&queue_position)
        || !atomic_is_lock_free(&deque_position)
        || !atomic_is_lock_free(&task_pointer)) {
        fail_message("the scheduler example requires lock-free C atomics");
    }
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

static void processor_relax(void) {
#if defined(__x86_64__) || defined(__i386__)
    _mm_pause();
#else
    atomic_signal_fence(memory_order_seq_cst);
#endif
}

static void wait_at_barrier(pthread_barrier_t *barrier) {
    int error_number = pthread_barrier_wait(barrier);
    if (error_number != 0 && error_number != PTHREAD_BARRIER_SERIAL_THREAD) {
        fail_errno("pthread_barrier_wait", error_number);
    }
}

static void pin_current_thread(int processor_id) {
    if (processor_id < 0) {
        return;
    }
    cpu_set_t processor_set;
    CPU_ZERO(&processor_set);
    CPU_SET((size_t)processor_id, &processor_set);
    int error_number = pthread_setaffinity_np(
        pthread_self(), sizeof(processor_set), &processor_set
    );
    if (error_number != 0) {
        fail_errno("pthread_setaffinity_np", error_number);
    }
}

static void initialize_mpmc_queue(MpmcQueue *queue) {
    queue->mask = example_queue_capacity - 1;
    queue->cells = allocate_aligned(
        example_cache_line_alignment,
        example_queue_capacity * sizeof(*queue->cells)
    );
    for (size_t position = 0; position < example_queue_capacity; ++position) {
        atomic_init(&queue->cells[position].sequence, position);
    }
    atomic_init(&queue->enqueue_position, 0);
    atomic_init(&queue->dequeue_position, 0);
}

static void destroy_mpmc_queue(MpmcQueue *queue) {
    free(queue->cells);
}

static bool try_enqueue_mpmc(MpmcQueue *queue, LiteralSchedulerTask *task) {
    QueueCell *cell;
    size_t position = atomic_load_explicit(
        &queue->enqueue_position, memory_order_relaxed
    );
    for (;;) {
        cell = &queue->cells[position & queue->mask];
        size_t sequence = atomic_load_explicit(&cell->sequence, memory_order_acquire);
        intptr_t difference = (intptr_t)sequence - (intptr_t)position;
        if (difference == 0) {
            if (atomic_compare_exchange_weak_explicit(
                    &queue->enqueue_position,
                    &position,
                    position + 1,
                    memory_order_relaxed,
                    memory_order_relaxed
                )) {
                break;
            }
        } else if (difference < 0) {
            return false;
        } else {
            position = atomic_load_explicit(
                &queue->enqueue_position, memory_order_relaxed
            );
        }
    }
    cell->task = task;
    atomic_store_explicit(&cell->sequence, position + 1, memory_order_release);
    return true;
}

static LiteralSchedulerTask *try_dequeue_mpmc(MpmcQueue *queue) {
    QueueCell *cell;
    size_t position = atomic_load_explicit(
        &queue->dequeue_position, memory_order_relaxed
    );
    for (;;) {
        cell = &queue->cells[position & queue->mask];
        size_t sequence = atomic_load_explicit(&cell->sequence, memory_order_acquire);
        intptr_t difference = (intptr_t)sequence - (intptr_t)(position + 1);
        if (difference == 0) {
            if (atomic_compare_exchange_weak_explicit(
                    &queue->dequeue_position,
                    &position,
                    position + 1,
                    memory_order_relaxed,
                    memory_order_relaxed
                )) {
                break;
            }
        } else if (difference < 0) {
            return NULL;
        } else {
            position = atomic_load_explicit(
                &queue->dequeue_position, memory_order_relaxed
            );
        }
    }
    LiteralSchedulerTask *task = cell->task;
    atomic_store_explicit(
        &cell->sequence, position + queue->mask + 1, memory_order_release
    );
    return task;
}

static void initialize_work_deque(WorkDeque *deque) {
    deque->mask = example_queue_capacity - 1;
    deque->tasks = allocate_aligned(
        example_cache_line_alignment,
        example_queue_capacity * sizeof(*deque->tasks)
    );
    atomic_init(&deque->top, 0);
    atomic_init(&deque->bottom, 0);
}

static void destroy_work_deque(WorkDeque *deque) {
    free(deque->tasks);
}

static void push_work_deque(WorkDeque *deque, LiteralSchedulerTask *task) {
    int64_t bottom = atomic_load_explicit(&deque->bottom, memory_order_relaxed);
    int64_t top = atomic_load_explicit(&deque->top, memory_order_acquire);
    if (bottom - top >= example_queue_capacity) {
        fail_message("work deque capacity exceeded");
    }
    atomic_store_explicit(
        &deque->tasks[bottom & deque->mask], task, memory_order_relaxed
    );
    atomic_thread_fence(memory_order_release);
    atomic_store_explicit(&deque->bottom, bottom + 1, memory_order_relaxed);
}

static LiteralSchedulerTask *pop_work_deque(WorkDeque *deque) {
    int64_t bottom = atomic_load_explicit(&deque->bottom, memory_order_relaxed) - 1;
    atomic_store_explicit(&deque->bottom, bottom, memory_order_relaxed);
    atomic_thread_fence(memory_order_seq_cst);
    int64_t top = atomic_load_explicit(&deque->top, memory_order_relaxed);
    if (top <= bottom) {
        LiteralSchedulerTask *task = atomic_load_explicit(
            &deque->tasks[bottom & deque->mask], memory_order_relaxed
        );
        if (top == bottom) {
            int64_t next_top = top + 1;
            if (!atomic_compare_exchange_strong_explicit(
                    &deque->top,
                    &top,
                    next_top,
                    memory_order_seq_cst,
                    memory_order_relaxed
                )) {
                task = NULL;
            }
            atomic_store_explicit(&deque->bottom, bottom + 1, memory_order_relaxed);
        }
        return task;
    }
    atomic_store_explicit(&deque->bottom, bottom + 1, memory_order_relaxed);
    return NULL;
}

static LiteralSchedulerTask *steal_work_deque(WorkDeque *deque) {
    int64_t top = atomic_load_explicit(&deque->top, memory_order_acquire);
    atomic_thread_fence(memory_order_seq_cst);
    int64_t bottom = atomic_load_explicit(&deque->bottom, memory_order_acquire);
    if (top >= bottom) {
        return NULL;
    }
    LiteralSchedulerTask *task = atomic_load_explicit(
        &deque->tasks[top & deque->mask], memory_order_relaxed
    );
    int64_t next_top = top + 1;
    if (!atomic_compare_exchange_strong_explicit(
            &deque->top,
            &top,
            next_top,
            memory_order_seq_cst,
            memory_order_relaxed
        )) {
        return NULL;
    }
    return task;
}

static void literal_join_initialize(LiteralJoin *join, unsigned int arrivals) {
    atomic_init(&join->remaining, arrivals);
}

static bool literal_join_arrive(LiteralJoin *join) {
    return atomic_fetch_sub_explicit(&join->remaining, 1, memory_order_acq_rel)
        == 1;
}

static uint64_t next_random(LiteralSchedulerWorker *worker) {
    uint64_t state = worker->random_state;
    state ^= state << 13;
    state ^= state >> 7;
    state ^= state << 17;
    worker->random_state = state;
    return state;
}

static void literal_scheduler_submit(
    LiteralSchedulerWorker *worker, LiteralSchedulerTask *task
) {
    LiteralScheduler *scheduler = worker->scheduler;
    if (task->preferred_group >= scheduler->group_count) {
        fail_message("scheduler task has an invalid preferred topology group");
    }
    if (task->preferred_group != worker->group
        && try_enqueue_mpmc(
            &scheduler->group_injection[task->preferred_group], task
        )) {
        return;
    }
    push_work_deque(&worker->deque, task);
}

static bool literal_scheduler_can_continue(
    const LiteralSchedulerWorker *worker,
    const LiteralSchedulerTask *continuation,
    bool prefer_topology_group
) {
    return !prefer_topology_group || continuation->preferred_group == worker->group;
}

static LiteralSchedulerTask *try_steal_from_workers(
    LiteralSchedulerWorker *worker, bool same_group
) {
    LiteralScheduler *scheduler = worker->scheduler;
    size_t start = next_random(worker) % scheduler->worker_count;
    for (size_t offset = 0; offset < scheduler->worker_count; ++offset) {
        size_t victim_index = (start + offset) % scheduler->worker_count;
        LiteralSchedulerWorker *victim = &scheduler->workers[victim_index];
        if (victim == worker) {
            continue;
        }
        if ((victim->group == worker->group) != same_group) {
            continue;
        }
        LiteralSchedulerTask *task = steal_work_deque(&victim->deque);
        if (task != NULL) {
            return task;
        }
    }
    return NULL;
}

static LiteralSchedulerTask *next_scheduler_task(LiteralSchedulerWorker *worker) {
    LiteralScheduler *scheduler = worker->scheduler;
    LiteralSchedulerTask *task = pop_work_deque(&worker->deque);
    if (task != NULL) {
        worker->failed_local_polls = 0;
        return task;
    }

    task = try_dequeue_mpmc(&scheduler->group_injection[worker->group]);
    if (task != NULL) {
        worker->failed_local_polls = 0;
        return task;
    }

    task = try_steal_from_workers(worker, true);
    if (task != NULL) {
        worker->failed_local_polls = 0;
        return task;
    }

    if (worker->failed_local_polls < scheduler->cross_group_poll_delay) {
        ++worker->failed_local_polls;
        return NULL;
    }
    worker->failed_local_polls = 0;

    for (size_t group = 0; group < scheduler->group_count; ++group) {
        if (group == worker->group) {
            continue;
        }
        task = try_dequeue_mpmc(&scheduler->group_injection[group]);
        if (task != NULL) {
            return task;
        }
    }
    return try_steal_from_workers(worker, false);
}

static void *run_scheduler_worker(void *opaque_worker) {
    LiteralSchedulerWorker *worker = opaque_worker;
    LiteralScheduler *scheduler = worker->scheduler;
    pin_current_thread(worker->processor_id);
    wait_at_barrier(&scheduler->start_barrier);

    LiteralSchedulerTask *task = NULL;
    for (;;) {
        if (task == NULL) {
            if (atomic_load_explicit(&scheduler->done.value, memory_order_acquire)) {
                break;
            }
            task = next_scheduler_task(worker);
            if (task == NULL) {
                processor_relax();
                continue;
            }
        }
        task = task->function(worker, task);
    }
    return NULL;
}

static void literal_scheduler_initialize(
    LiteralScheduler *scheduler, const LiteralSchedulerConfig *config
) {
    if (config->worker_count == 0
        || config->worker_count > example_maximum_workers) {
        fail_message("invalid scheduler worker count");
    }
    if (config->group_count == 0
        || config->group_count > example_maximum_topology_groups
        || config->group_count > config->worker_count) {
        fail_message("invalid scheduler topology group count");
    }

    memset(scheduler, 0, sizeof(*scheduler));
    scheduler->worker_count = config->worker_count;
    scheduler->group_count = config->group_count;
    scheduler->cross_group_poll_delay = config->cross_group_poll_delay;
    atomic_init(&scheduler->done.value, false);

    require_lock_free_scheduler_atomics();

    bool group_has_worker[example_maximum_topology_groups] = {false};
    for (size_t group = 0; group < scheduler->group_count; ++group) {
        initialize_mpmc_queue(&scheduler->group_injection[group]);
    }
    for (size_t worker_index = 0; worker_index < scheduler->worker_count;
         ++worker_index) {
        uint16_t group = config->group_ids[worker_index];
        if (group >= scheduler->group_count) {
            fail_message("scheduler worker has an invalid topology group");
        }
        group_has_worker[group] = true;
        LiteralSchedulerWorker *worker = &scheduler->workers[worker_index];
        worker->scheduler = scheduler;
        worker->index = worker_index;
        worker->processor_id = config->processor_ids[worker_index];
        worker->group = group;
        worker->random_state = UINT64_C(0x2545f4914f6cdd1d)
            ^ (worker_index * UINT64_C(0x9e3779b97f4a7c15));
        initialize_work_deque(&worker->deque);
    }
    for (size_t group = 0; group < scheduler->group_count; ++group) {
        if (!group_has_worker[group]) {
            fail_message("scheduler topology group has no workers");
        }
    }

    int error_number = pthread_barrier_init(
        &scheduler->start_barrier,
        NULL,
        (unsigned int)scheduler->worker_count + 1
    );
    if (error_number != 0) {
        fail_errno("pthread_barrier_init", error_number);
    }
}

static void literal_scheduler_finish(LiteralSchedulerWorker *worker) {
    atomic_store_explicit(&worker->scheduler->done.value, true, memory_order_release);
}

static void literal_scheduler_run(
    LiteralScheduler *scheduler, LiteralSchedulerTask *initial_task
) {
    if (initial_task->preferred_group >= scheduler->group_count) {
        fail_message("initial scheduler task has an invalid preferred topology group");
    }

    LiteralSchedulerWorker *initial_worker = NULL;
    for (size_t worker_index = 0; worker_index < scheduler->worker_count;
         ++worker_index) {
        LiteralSchedulerWorker *worker = &scheduler->workers[worker_index];
        if (worker->group == initial_task->preferred_group) {
            initial_worker = worker;
            break;
        }
    }
    if (initial_worker == NULL) {
        fail_message("no worker matches the initial scheduler task");
    }
    push_work_deque(&initial_worker->deque, initial_task);

    pthread_t threads[example_maximum_workers];
    for (size_t worker_index = 0; worker_index < scheduler->worker_count;
         ++worker_index) {
        int error_number = pthread_create(
            &threads[worker_index],
            NULL,
            run_scheduler_worker,
            &scheduler->workers[worker_index]
        );
        if (error_number != 0) {
            fail_errno("pthread_create", error_number);
        }
    }
    wait_at_barrier(&scheduler->start_barrier);
    for (size_t worker_index = 0; worker_index < scheduler->worker_count;
         ++worker_index) {
        int error_number = pthread_join(threads[worker_index], NULL);
        if (error_number != 0) {
            fail_errno("pthread_join", error_number);
        }
    }
}

static void literal_scheduler_destroy(LiteralScheduler *scheduler) {
    int error_number = pthread_barrier_destroy(&scheduler->start_barrier);
    if (error_number != 0) {
        fail_errno("pthread_barrier_destroy", error_number);
    }
    for (size_t worker_index = 0; worker_index < scheduler->worker_count;
         ++worker_index) {
        destroy_work_deque(&scheduler->workers[worker_index].deque);
    }
    for (size_t group = 0; group < scheduler->group_count; ++group) {
        destroy_mpmc_queue(&scheduler->group_injection[group]);
    }
}

typedef struct ExampleGraph ExampleGraph;

typedef struct {
    ExampleGraph *graph;
    size_t particle_index;
    LiteralSchedulerTask task;
} ExampleLeaf;

struct ExampleGraph {
    LiteralJoin join;
    uint64_t particles[2];
    unsigned int continuation_runs;
    LiteralSchedulerTask start;
    ExampleLeaf leaves[2];
    LiteralSchedulerTask continuation;
};

static LiteralSchedulerTask *run_example_continuation(
    LiteralSchedulerWorker *worker, LiteralSchedulerTask *task
) {
    ExampleGraph *graph = task->context;
    if (graph->particles[0] != 41 || graph->particles[1] != 42) {
        fail_message("the Join did not publish every Particle write");
    }
    ++graph->continuation_runs;
    literal_scheduler_finish(worker);
    return NULL;
}

static LiteralSchedulerTask *run_example_leaf(
    LiteralSchedulerWorker *worker, LiteralSchedulerTask *task
) {
    ExampleLeaf *leaf = task->context;
    ExampleGraph *graph = leaf->graph;
    graph->particles[leaf->particle_index] = 41 + leaf->particle_index;
    if (!literal_join_arrive(&graph->join)) {
        return NULL;
    }
    if (literal_scheduler_can_continue(
            worker, &graph->continuation, true
        )) {
        return run_example_continuation(worker, &graph->continuation);
    }
    literal_scheduler_submit(worker, &graph->continuation);
    return NULL;
}

static LiteralSchedulerTask *run_example_start(
    LiteralSchedulerWorker *worker, LiteralSchedulerTask *task
) {
    ExampleGraph *graph = task->context;
    literal_scheduler_submit(worker, &graph->leaves[1].task);
    return run_example_leaf(worker, &graph->leaves[0].task);
}

static void initialize_example_graph(ExampleGraph *graph) {
    memset(graph, 0, sizeof(*graph));
    literal_join_initialize(&graph->join, 2);
    graph->start = (LiteralSchedulerTask){
        .function = run_example_start,
        .context = graph,
        .preferred_group = 0,
    };
    graph->continuation = (LiteralSchedulerTask){
        .function = run_example_continuation,
        .context = graph,
        .preferred_group = 0,
    };
    for (size_t particle_index = 0; particle_index < 2; ++particle_index) {
        graph->leaves[particle_index] = (ExampleLeaf){
            .graph = graph,
            .particle_index = particle_index,
            .task = {
                .function = run_example_leaf,
                .context = &graph->leaves[particle_index],
                .preferred_group = (uint16_t)particle_index,
            },
        };
    }
}

int main(void) {
    LiteralSchedulerConfig config;
    memset(&config, 0, sizeof(config));
    config.worker_count = 2;
    config.group_count = 2;
    config.group_ids[1] = 1;
    config.cross_group_poll_delay = 64;
    for (size_t worker_index = 0; worker_index < example_maximum_workers;
         ++worker_index) {
        config.processor_ids[worker_index] = -1;
    }

    LiteralScheduler scheduler;
    literal_scheduler_initialize(&scheduler, &config);
    ExampleGraph graph;
    initialize_example_graph(&graph);
    literal_scheduler_run(&scheduler, &graph.start);
    literal_scheduler_destroy(&scheduler);

    if (graph.continuation_runs != 1) {
        fail_message("the Join continuation did not run exactly once");
    }
    return EXIT_SUCCESS;
}
