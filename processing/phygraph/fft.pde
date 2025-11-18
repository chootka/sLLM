/**
  * Ben-FFT was written by: Ben-Tommy Eriksen ben@nornet.no
  * 
  * I want to develop a fast Fourier transform FFT for processing from scratch.
  * A fast Fourier transform (FFT) is an algorithm to compute the discrete Fourier 
  * transform (DFT) and it's inverse. http://en.wikipedia.org/wiki/Fast_Fourier_transform
  *
  * Much of the theory is obtained from: The Scientist and Engineer's Guide to Digital 
  * Signal Processing By Steven W. Smith, Ph.D. http://www.dspguide.com
  */
class BenFFT {
  int N; // Instance variable for sample count
  
  BenFFT (int _N) {
    N = _N;
    // Initialize arrays with proper size
    XR = new float[N]; // Input Time domain - sample data 
    XI = new float[N]; // Input Time domain - sample data Complex part
    XOut = new float[N]; // Output frequency domain data
    ReX = new float[N];
    ImX = new float[N];
    TR = new float[1];
    TI = new float[1];
    
    // Calculate derived values
    NM1 = N - 1;
    NM2 = N - 2;
    ND2 = N / 2;
    M = round(log(N)/log(2));
    J = ND2;
    ToppF = 0;
  }
  
  float[] XR; // Input Time domain - sample data 
  float[] XI; // Input Time domain - sample data Complex part
  float[] XOut; // Output frequency domain data

  float[] ReX;
  float[] ImX;
  float[] TR;
  float[] TI;
  
  
  int NM1;
  int NM2;
  int ND2;
  int M;
  
  int J;
  
  int ToppF;

  
  float[] XR() {
    // Output Input Time domain - sample data 
    return XR; 
  }
  
  float[] XOut() {
    // Output frequency domain data
    return XOut; 
  }
  
  
  
  int ToppF() {
    // Find most dominant frequence
    return ToppF;
  }
  
  void oneSample(float sample) {
    
    // Shift old data to the left
    for(int i = 1; i < N; i++) {
      arrayCopy(XR,i,XR,i-1,1);
    }
    
    XR[N-1] = sample; // add data at the end of the array N/2
  }
  

  void sendHertz(float hz, float[] hertzArray, int viewHertzSize){
     for(int i = 1; i < viewHertzSize; i++) {
      arrayCopy(hertzArray,i,hertzArray,i-1,1);
    }
    
    hertzArray[viewHertzSize-1] = hz;
  }
  
  void setInDataArr(float[] InData) {
    XR = InData;
    
  }

  void fft() {
    // Moving data from XR and MI to ReX and ImX and reverse place them
    for(int i = 0; i < N; i++) {
      J = getBitRevNr(i,M);
      arrayCopy(XR,J,ReX,i,1);   // ReX[i] = TR[0];
      arrayCopy(XI,J,ImX,i,1);   // ImX[i] = TI[0];
    }
    
    // Start FFT calculation
   int LE,LE2;
   float UR,UI,SR,SI,TR,TI;
   float Now = 0;
   float nowHi = 0;
   int TopFequence;
   float FTopp = 0;
   for(int L = 1; L<=M; L++) {
     LE = int(pow(2,L));
     LE2 = LE/2;
     UR = 1.0;
     UI = 0;
     SR = cos(PI/LE2);
     SI = -sin(PI/LE2);
     
     for(int J = 1; J<LE2; J++) {
       int JM1 = J-1;
       for(int i = JM1; i<=NM1; i = i + LE) {
         int IP = i + LE2;
         TR = ReX[IP] * UR - ImX[IP] * UI;
         TI = ReX[IP] * UI + ImX[IP] * UR;
         ReX[IP] = ReX[i] - TR;
         ImX[IP] = ImX[i] - TI;
         ReX[i] = ReX[i] + TR;
         ImX[i] = ImX[i] + TI;
       }
       TR = UR;
       UR = TR*SR - UI*SI;
       UI = TR*SI + UI*SR;
     }
    }
    for(int L = 1; L<=ND2; L++) {
      Now = abs(ReX[L]) + abs(ImX[L]);
      if(Now>nowHi && L>1) {
        nowHi = Now;
        ToppF = L;
      }
      XOut[L] = Now;
    } 
  }
}

int getBitRevNr(int bitNr,int M) {
  
  // calculate the revers number in fft sequence
  
  int Ndigits = M;                                  // Number of digits in the binary format of sample count N
  int revBitNr;
  int tempBit;
  int resultat = 0;
  for(int iBit = 0; iBit<Ndigits; iBit++) {         // search bit for bit from right to left
    tempBit = bitNr & int(pow(2,iBit));             // take out current bit value 
    if(tempBit>0) {                                 // if bit value = 1
      revBitNr = Ndigits - iBit - 1;                // calculate rev bit place
      resultat = resultat | int(pow(2,revBitNr));   // put current bit in new place in result (with or)
    }
  }
  return resultat;
}
