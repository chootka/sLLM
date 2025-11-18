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
  
  BenFFT (int _N) {
    int N = _N;
  }
  float[] XR = new float[N]; // Input Time domain - sample data 
  float[] XI = new float[N]; // Input Time domain - sample data Complex part
  float[] XOut = new float[N]; // Output frequency domain data

  float[] ReX = new float[N];
  float[] ImX = new float[N];
  float[] TR = new float[1];
  float[] TI = new float[1];
  
  
  int NM1 = N - 1;
  int NM2 = N - 2;
  int ND2 = N / 2;
  int M = round(log(N)/log(2));
  
  int J = ND2;
  
  int ToppF = 0;

  
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
  

  void sendHertz(float hz){
     for(int i = 1; i < viewHertzSize; i++) {
      arrayCopy(hertzArray,i,hertzArray,i-1,1);
    }
    
    hertzArray[viewHertzSize-1] = hertz;
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
