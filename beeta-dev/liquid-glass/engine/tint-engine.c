#include <stdio.h>
#include <stdlib.h>

int main() {

    FILE *fp;
    char color[64];

    fp = popen("convert ~/wallpaper.jpg -resize 1x1 txt:- | grep -o '#[0-9A-Fa-f]\\{6\\}'", "r");

    if (fp == NULL) {
        printf("Failed to run command\n");
        return 1;
    }

    fgets(color, sizeof(color), fp);

    printf("Beeta Glass Tint: %s\n", color);

    pclose(fp);

    return 0;
}
