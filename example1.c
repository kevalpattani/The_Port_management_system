#include<stdio.h>
#include<stdlib.h>
#include<math.h>

//a rectangula region
typedef struct rectangular_region
{
    char state;
    int x1;
    int x2;
    int y1;
    int y2; 
}Rreg;

// Function to print the layout with regions

void print_grid_flat(Rreg rules[], int size, int grid_size){
    char t;
    for(int i = 0; i <= grid_size; i++){
        for(int j = 0; j <= grid_size; j++){
            t = ' ';
            for(int k = 0; k < size; k++)
                if( rules[k].x1 <= i && rules[k].x2 >= i && rules[k].y1 <= j && rules[k].y2 >= j )
                    if(rules[k].state == 'o') t = 'O';
                    else t = 'F';  
            printf("%c",t);
        }
        printf("\n");
    }
}

void print_grid_document(Rreg rules[], int size, char a[]){

}

void print_grid_function(Rreg rules[], int size, int grid_size, int (*funct)(int, int), int presision){
    char gradient[] = " .:-=+*#$@";
    char t;
    for(int i = 0; i <= grid_size; i++){
        for(int j = 0; j <= grid_size; j++){
            t = ' ';
            for(int k = 0; k < size; k++){
                if( rules[k].x1 <= i && rules[k].x2 >= i && rules[k].y1 <= j && rules[k].y2 >= j ){
                    if(rules[k].state == 'o') t = 'O';
                    else t = 'F';
                }
                else
                    t = gradient[funct(i,j)*presision];
            }
            printf("%c",t);
        }
        printf("\n");
    }
}


int sample_funct(int a, int b){
    return ((a*a+b*b)/1000);
}

int main(){

    //definig each rule/rectangualr region
    Rreg rule1 = {'o', 20, 60, 4, 10};        //defines a rectangular region with x1,x2 and y1,y2 (for now n=by the 4th quadrent)
    Rreg rule2 = {'u', 10, 14, 7, 56};

    
    // collection of rules/rectangual regions
    Rreg rules[] = {rule1, rule2};

    //displing the rules (for now wth the complexisty of n^3 yuck!)
    //print_grid_flat(rules, sizeof(rules)/sizeof(rules[0]), 100);

    //using some baground, needs refinment
    print_grid_function(rules, 2, 100, sample_funct, 1); // problem --> this is only printing rules[1] 
    return 0;
}