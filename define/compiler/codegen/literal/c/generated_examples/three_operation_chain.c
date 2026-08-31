static unsigned char test_particle;
static unsigned char item_then_dest_particle;

static void destroy_dest(void) {
    item_then_dest_particle = 0;
}

static void move_item_to_dest(void) {
    /* A Move changes the generated Position name, not the Particle's address. */
    destroy_dest();
}

static void create_item(void) {
    item_then_dest_particle = 1;
    move_item_to_dest();
}

static void action_test(void) {
    create_item();
}

int main(void) {
    test_particle = 1;
    action_test();
    return 0;
}
