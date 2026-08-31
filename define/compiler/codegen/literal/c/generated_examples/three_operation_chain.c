static unsigned char test_particle;
static unsigned char item_then_dest_particle;

static void action_test(void) {
    item_then_dest_particle = 1;

    /* A Move changes the generated Position name, not the Particle's address. */
    item_then_dest_particle = 0;
}

int main(void) {
    test_particle = 1;
    action_test();
    return 0;
}
