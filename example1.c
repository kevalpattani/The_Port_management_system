#include<stdio.h>
#include<stdlib.h>
#include<math.h>

//a rectangula region
typedef struct rectangular_region{
    char state;
    int x1;
    int x2;
    int y1;
    int y2; 
}Rreg;

typedef struct moving_object{
    char type[];
    int x;
    int y;
}movobj;

// Function to print the layout with regions

void print_grid_flat(Rreg rules[], int size, int grid_size){
    for(int i = 0; i <= grid_size; i++){
        for(int j = 0; j <= grid_size; j++){
            for(int k = 0; k < size; k++){
                if( rules[k].x1 <= i && rules[k].x2 >= i && rules[k].y1 <= j && rules[k].y2 >= j ){
                    if(rules[k].state == 'o')
                        printf("%s%c", "\033[31m",'O');
                    else
                       printf("%s%c", "\033[35m",'F');  
                }
                else
                    printf("\033[0m"); 
            }
        }
        printf("\n");
    }
}

void print_grid_doc(Rreg rules[], int size, char a[]){

}

void print_grid_function(Rreg rules[], int size, int grid_size, int (*funct)(int, int), int presision){
    const char gradient[] = " .:-=+*#$@";

    for(int i = 0; i <= grid_size; i++){
        for(int j = 0; j <= grid_size; j++){
            int flag = 0;
            for(int k = 0; k < size; k++){
                if( rules[k].x1 <= i && rules[k].x2 >= i && rules[k].y1 <= j && rules[k].y2 >= j ){
                    if(rules[k].state == 'o'){
                        printf("%s%c", "\033[31m",'O'); flag = 1;}
                    else{
                       printf("%s%c", "\033[35m",'F');  flag = 1;}
                }
            }
            if(flag == 0){
                    if(funct(i,j)*presision < 10)
                        printf("%c\033[37m",gradient[funct(i,j)*presision]);
                    else
                        printf("\033[37mE"); 
                }
        }
        printf("\n");
    }
}


int sample_funct(int a, int b){
    return ((a*b+b)/10);
}

int main(){

    movobj fight1 = {"airoplane","2","3"};
    movobj flight2 = {"airoplane", "5", "6"};

    //definig each rule/rectangualr region
    Rreg rule1 = {'o', 20, 60, 4, 10};        //defines a rectangular region with x1,x2 and y1,y2 (for now n=by the 4th quadrent)
    Rreg rule2 = {'u', 10, 14, 7, 56};

    
    // collection of rules/rectangual regions
    Rreg rules[] = {rule1, rule2};

    //displing the rules 
    print_grid_flat(rules, sizeof(rules)/sizeof(rules[0]), 50);

    //using some background, needs refinment
    print_grid_function(rules, 2, 50, sample_funct, 1); 
    return 0;
}