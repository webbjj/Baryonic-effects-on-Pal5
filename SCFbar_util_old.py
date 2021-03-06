import glob
import pickle
import numpy
import numpy as np
from numpy.polynomial import Polynomial
from scipy import ndimage, signal, interpolate, integrate
from galpy.orbit import Orbit
from galpy.potential import MWPotential2014, turn_physical_off, MiyamotoNagaiPotential, plotDensities,evaluateDensities,plotPotentials
from galpy.util import bovy_conversion, save_pickles, bovy_coords, bovy_plot
import pal5_util
#import gd1_util
#from gd1_util import R0, V0
#import custom_stripping_df
import seaborn as sns
import astropy.units as u
from galpy import potential
from matplotlib import cm, pyplot
from galpy.potential import DehnenSmoothWrapperPotential as DehnenWrap
from galpy.potential import SCFPotential
import streamspraydf

ro=8.
vo=220.

#List of important functions

#compute_Acos_Asin(n=9,l=19,a=1./ro,radial_order=40,costheta_order=40,phi_order=40)

#MWPotentialSCFbar(mbar,Acos,Asin,rs=1.,normalize=False,pat_speed=40.,fin_phi_deg=27.,t_stream_age=5.,t_on=2.,tgrow=2)

#MWPotentialSCFbar_invert(mbar,Acos,Asin,rs=1.,normalize=False,pat_speed=40.,fin_phi_deg=27.,t_stream_age=5.,t_on=2.,tgrow=2)

   

#setup the bar

#compute normalization 
#constants
x0=1.49 # kpc
y0=0.58
z0=0.4
q= 0.6

Mbar=10**10 #Msun, half of what Wang is using, same as Pearson

def tform_from_t_on(t_on=2.,pat_speed=40.,tgrow=2):
        
    omegaP=pat_speed*(ro/vo)    
    Tbar=2.*np.pi/omegaP #bar period in galpy units.
    t_on=t_on/bovy_conversion.time_in_Gyr(vo,ro)
    tsteady=tgrow*Tbar
    tform = t_on + tsteady
    return tform #in galpy units


def rho1(R,z):
    return (2.*np.pi*x0*y0)*R*np.exp(-0.5*(np.sqrt(R**4 + (z/z0)**4)))

rho1norm= integrate.nquad(rho1,[[0,np.inf],[-np.inf,np.inf]])[0]

def rho2(R):
    return (z0**1.85 *4.*np.pi/q**2)*R**(0.15)*np.exp(-R/z0)

rho2norm= integrate.quad(rho2,0,np.inf)[0]
rho0=Mbar/(rho1norm + rho2norm)

def r1c(R,z,p):
    return ((R**4.)*(np.cos(p)**2./x0**2 + np.sin(p)**2/y0**2)**2 + (z/z0)**4.)**(0.25)

def r2c(R,z):
    return np.sqrt((q*R)**2. + z**2.)/z0


def rho_bar_cyl(R,z,p):
    return rho0*(np.exp((-r1c(R,z,p)**2.)/2.) + r2c(R,z)**(-1.85)*np.exp(-r2c(R,z)))


#compute SCF expansion coeffs
def compute_Acos_Asin(n=9,l=19,a=1./ro,radial_order=40,costheta_order=40,phi_order=40):
    
    Acos,Asin= potential.scf_compute_coeffs(lambda R,z,p: rho_bar_cyl(R*8.,z*8.,p)/(10**9.*bovy_conversion.dens_in_msolpc3(220.,8.)),
                                        N=n+1,L=l+1,a=a,radial_order=radial_order,costheta_order=costheta_order,phi_order=phi_order)
                                        
    return (Acos,Asin)
    
    
#setup no grow bar, just for book keeping

def MWPotentialSCFbar_nogrow(mbar,Acos,Asin,rs=1.,normalize=False,pat_speed=40.,fin_phi_deg=27.,t_stream_age=5.):
    
    a=rs/ro
    omegaP=pat_speed*(ro/vo)
    
    fin_phi= np.radians(fin_phi_deg)
    #init_phi= fin_phi - o_p*(tpal5age*Gyr_to_s)
    
    init_phi= fin_phi - omegaP*t_stream_age/bovy_conversion.time_in_Gyr(vo,ro)
    
    mrat=mbar/10.**10. #10^10 mass of bar used to compute Acos and Asin
    
    static_bar=potential.SCFPotential(amp=mrat,Acos=Acos,Asin=Asin,a=a,normalize=normalize)
    
    #Note only m=0 terms are considered 
    static_axi_bar=potential.SCFPotential(amp=mrat,Acos=np.atleast_3d(Acos[:,:,0]),a=a)
    
    barrot=potential.SolidBodyRotationWrapperPotential(pot=static_bar,omega=omegaP,ro=ro,vo=vo,pa=init_phi)
    
    if mbar <= 5.*10**9. :
        MWP2014SCFbar=[MWPotential2014[0],MiyamotoNagaiPotential(amp=(6.8-mrat)*10.**10*u.Msun,a=3./8.,b=0.28/8.),MWPotential2014[2],barrot]
        turn_physical_off(MWP2014SCFbar)
        #setup the corresponding axisymmetric bar
        MWP2014SCFnobar= [MWPotential2014[0],MiyamotoNagaiPotential(amp=(6.8-mrat)*10.**10*u.Msun,a=3./8.,b=0.28/8.),MWPotential2014[2],static_axi_bar]
        turn_physical_off(MWP2014SCFnobar)
        
    else : 
        MWP2014SCFbar=[MiyamotoNagaiPotential(amp=(6.8+0.5-mrat)*10.**10*u.Msun,a=3./8.,b=0.28/8.),MWPotential2014[2],barrot]
        turn_physical_off(MWP2014SCFbar)
        
        MWP2014SCFnobar= [MiyamotoNagaiPotential(amp=(6.8+0.5-mrat)*10.**10*u.Msun,a=3./8.,b=0.28/8.),MWPotential2014[2],static_axi_bar]
        turn_physical_off(MWP2014SCFnobar)
        
    return (MWP2014SCFbar,MWP2014SCFnobar)
    
    
def MWPotentialSCFbar(mbar,Acos,Asin,rs=1.,normalize=False,pat_speed=40.,fin_phi_deg=27.,t_stream_age=5.,t_on=2.,tgrow=2):
    
    '''
    t_stream_age : age of the stream/max stripping time
    t_on: time in Gyr in the past at which the bar acquired full strength
    tgrow: no of bar periods it took the bar to grow to full strength starting at tform
            
    '''
    
    #setup the full strength bar and axisymmetric "bar"
    a=rs/ro
    omegaP=pat_speed*(ro/vo)
    
    fin_phi= np.radians(fin_phi_deg)
    
    t_stream_age=t_stream_age/bovy_conversion.time_in_Gyr(vo,ro)
    
    Tbar=2.*np.pi/omegaP #bar period in galpy units.
    t_on=t_on/bovy_conversion.time_in_Gyr(vo,ro)
    tsteady=tgrow*Tbar
    tform = t_on + tsteady
        
    init_phi= fin_phi - omegaP*t_stream_age/bovy_conversion.time_in_Gyr(vo,ro)
    
    mrat=mbar/10.**10. #10^10 mass of bar used to compute Acos and Asin
    
    static_bar=SCFPotential(amp=mrat,Acos=Acos,Asin=Asin,a=a,normalize=normalize)
    
    #Note only m=0 terms are considered 
    static_axi_bar=SCFPotential(amp=mrat,Acos=np.atleast_3d(Acos[:,:,0]),a=a)
    
    barrot=potential.SolidBodyRotationWrapperPotential(pot=static_bar,omega=omegaP,ro=ro,vo=vo,pa=init_phi)
    
    if mbar <= 5.*10**9. :
        MWP2014SCFbar=[MWPotential2014[0],MiyamotoNagaiPotential(amp=(6.8-mrat)*10.**10*u.Msun,a=3./8.,b=0.28/8.),MWPotential2014[2],barrot]
        turn_physical_off(MWP2014SCFbar)
        #setup the corresponding axisymmetric bar
        MWP2014SCFnobar= [MWPotential2014[0],MiyamotoNagaiPotential(amp=(6.8-mrat)*10.**10*u.Msun,a=3./8.,b=0.28/8.),MWPotential2014[2],static_axi_bar]
        turn_physical_off(MWP2014SCFnobar)
        
    else : 
        MWP2014SCFbar=[MiyamotoNagaiPotential(amp=(6.8+0.5-mrat)*10.**10*u.Msun,a=3./8.,b=0.28/8.),MWPotential2014[2],barrot]
        turn_physical_off(MWP2014SCFbar)
        
        MWP2014SCFnobar= [MiyamotoNagaiPotential(amp=(6.8+0.5-mrat)*10.**10*u.Msun,a=3./8.,b=0.28/8.),MWPotential2014[2],static_axi_bar]
        turn_physical_off(MWP2014SCFnobar)
        
    
    #setup Dehnen smooth growth wrapper for the bar
    #convert to galpy units
    

    
    
    #if t_on >= t_pal5_age, then Pal 5 sees the bar as always on
    if t_on >= t_stream_age :
        return (MWP2014SCFbar,MWP2014SCFnobar)
    
    elif tform >= t_stream_age:
        print ("tform > age of Pal 5 stream")
        
    elif tform < t_stream_age :
           
        #change tform in the past, i.e. instead of from today, to time in the future from 5 Gyr in the past
        tform=t_stream_age-tform
        MWbar_grow=DehnenWrap(amp=1.,pot=MWP2014SCFbar,tform=tform,tsteady=tsteady)  
        MWaxibar_destroy=DehnenWrap(amp=-1.,pot=MWP2014SCFnobar,tform=tform,tsteady=tsteady) 
       
        growbarpot=[MWbar_grow,MWP2014SCFnobar,MWaxibar_destroy]
        
        turn_physical_off(growbarpot)
    
        return (growbarpot,MWP2014SCFnobar)
    

def MWPotentialSCFbar_invert(mbar,Acos,Asin,rs=1.,normalize=False,pat_speed=40.,fin_phi_deg=27.,t_stream_age=5.,t_on=2.,tgrow=2):
    
    '''
    t_stream_age : age of the stream/max stripping time
    tform: time in Gyr in the past at which the bar started to form
    tgrow: no of bar periods it took the bar to grow to full strength starting at tform
    
        
    '''
    
    #setup the full strength bar and axisymmetric "bar"
    a=rs/ro
    omegaP=pat_speed*(ro/vo)
    
    fin_phi= np.radians(fin_phi_deg)
        
    mrat=mbar/10.**10. #10^10 mass of bar used to compute Acos and Asin
    
    static_bar=potential.SCFPotential(amp=mrat,Acos=Acos,Asin=Asin,a=a,normalize=normalize)
    
    #Note only m=0 terms are considered 
    static_axi_bar=potential.SCFPotential(amp=mrat,Acos=np.atleast_3d(Acos[:,:,0]),a=a)
    
    #pa = final phi and omega is negative since we are going back in time
    barrot=potential.SolidBodyRotationWrapperPotential(pot=static_bar,omega=-omegaP,ro=ro,vo=vo,pa=fin_phi)
    
    if mbar <= 5.*10**9. :
        MWP2014SCFbar=[MWPotential2014[0],MiyamotoNagaiPotential(amp=(6.8-mrat)*10.**10*u.Msun,a=3./8.,b=0.28/8.),MWPotential2014[2],barrot]
        turn_physical_off(MWP2014SCFbar)
        #setup the corresponding axisymmetric bar
        MWP2014SCFnobar= [MWPotential2014[0],MiyamotoNagaiPotential(amp=(6.8-mrat)*10.**10*u.Msun,a=3./8.,b=0.28/8.),MWPotential2014[2],static_axi_bar]
        turn_physical_off(MWP2014SCFnobar)
        
    else : 
        MWP2014SCFbar=[MiyamotoNagaiPotential(amp=(6.8+0.5-mrat)*10.**10*u.Msun,a=3./8.,b=0.28/8.),MWPotential2014[2],barrot]
        turn_physical_off(MWP2014SCFbar)
        
        MWP2014SCFnobar= [MiyamotoNagaiPotential(amp=(6.8+0.5-mrat)*10.**10*u.Msun,a=3./8.,b=0.28/8.),MWPotential2014[2],static_axi_bar]
        turn_physical_off(MWP2014SCFnobar)
        
    
    #setup Dehnen smooth growth wrapper for the bar
    
    #while going back, t_on = tform, then deconstruct the bar to no bar during tsteady
    tform=t_on/bovy_conversion.time_in_Gyr(vo,ro)
    
    Tbar=2.*np.pi/omegaP
    tsteady=tgrow*Tbar
    
    MWaxibar_grow=DehnenWrap(amp=1.,pot=MWP2014SCFnobar,tform=tform,tsteady=tsteady)  
    MWbar_destroy=DehnenWrap(amp=-1.,pot=MWP2014SCFbar,tform=tform,tsteady=tsteady) 
       
    growbarpot_invert=[MWP2014SCFbar,MWaxibar_grow,MWbar_destroy]
    turn_physical_off(growbarpot_invert)
    
    return growbarpot_invert   
    
    
    


def sample_perturbed_Pal5(N,barpot,barpot_invert,nobarpot,prog_barpot,prog_barpot_invert,prog_nobarpot,fo='blah_trailing.dat',trailing=True,tpal5age=5.,t_on=2.,tgrow=2,pat_speed=40.):
    #Sample N points from the smooth model today 
    
    tpal5age=tpal5age/bovy_conversion.time_in_Gyr(220.,8.)
       
    if trailing :
          sdf_trailing= pal5_util.setup_pal5model(pot=nobarpot)
   
          R,vR,vT,z,vz,phi,dt= sdf_trailing.sample(n=N,returndt=True)
          fo=open(fo,'w')
        
    else :
          sdf_leading= pal5_util.setup_pal5model(pot=nobarpot,leading=True)
          R,vR,vT,z,vz,phi,dt= sdf_leading.sample(n=N,returndt=True)
          fo_lead=fo.replace('trailing','leading')
          fo=open(fo_lead,'w')
        
    tage=numpy.linspace(0.,tpal5age,1001)
    
    #integrate Pal 5 progenitor in barpot all the way back to 5 Gyrs, 
    #from this orbits will be extracted by interpolation in the for loop
    pal5_bar= Orbit([229.018,-0.124,23.2,-2.296,-2.257,-58.7],radec=True,solarmotion=[-11.1,24.,7.25]).flip() 
    pal5_bar.integrate(tage,prog_barpot_invert)
    
            
    #integrate Pal 5 progenitor in nobarpot all the way back to 5 Gyrs, 
    #from this orbits will be extracted by interpolation in the for loop   
    pal5_nobar= Orbit([229.018,-0.124,23.2,-2.296,-2.257,-58.7],radec=True,solarmotion=[-11.1,24.,7.25]).flip() 
    pal5_nobar.integrate(tage,prog_nobarpot)
    
    pal5_bar.turn_physical_off()
    pal5_nobar.turn_physical_off()
    
    finalR= numpy.empty(N)
    finalvR=numpy.empty(N)
    finalvT=numpy.empty(N)
    finalvz=numpy.empty(N)
    finalphi= numpy.empty(N)
    finalz= numpy.empty(N)
    tt=numpy.empty(N)

    tform = tform_from_t_on(t_on=t_on,pat_speed=pat_speed,tgrow=tgrow) #in galpy
    t_on=t_on/bovy_conversion.time_in_Gyr(220.,8.)

    for ii in range(N):
        
        o= Orbit([R[ii],vR[ii],vT[ii],z[ii],vz[ii],phi[ii]]).flip() # flip flips the velocities for backwards integration
        o.turn_physical_off()
        ts= numpy.linspace(0.,dt[ii],1001)
    
        #for integrating in barpot, time starts 5 Gyrs in the past and goes forward
        ts_future= numpy.linspace(tpal5age - dt[ii],tpal5age,1001)
    
        o.integrate(ts,nobarpot)
        #unp_orb=o(ts[-1]).flip()._orb.vxvv
        
        #extract the orbit at the stripping time from the above integrated orbit
        #pal5_orb_bar = pal5_bar(ts[-1]).flip()._orb.vxvv
        #pal5_orb_nobar = pal5_nobar(ts[-1]).flip()._orb.vxvv
        
        unp_orb=numpy.array([o.x(ts[-1]),o.y(ts[-1]),o.z(ts[-1]),-o.vx(ts[-1]),-o.vy(ts[-1]),-o.vz(ts[-1])])
        pal5_orb_bar= numpy.array([pal5_bar.x(ts[-1]),pal5_bar.y(ts[-1]),pal5_bar.z(ts[-1]),-pal5_bar.vx(ts[-1]),-pal5_bar.vy(ts[-1]),-pal5_bar.vz(ts[-1])])
        pal5_orb_nobar= numpy.array([pal5_nobar.x(ts[-1]),pal5_nobar.y(ts[-1]),pal5_nobar.z(ts[-1]),-pal5_nobar.vx(ts[-1]),-pal5_nobar.vy(ts[-1]),-pal5_nobar.vz(ts[-1])])
        
        #print (unp_orb)
        #print (pal5_orb_bar)  
        #print (pal5_orb_nobar)
              
        #subtract Pal 5 orb in nobarpot and add Pal 5 orbit in barpot
        #pert_orb=(np.array(unp_orb) - np.array(pal5_orb_nobar)) + np.array(pal5_orb_bar)
        #pert_orb=Orbit(list(pert_orb))
        
        pert_orb= unp_orb - pal5_orb_nobar + pal5_orb_bar
        
        print (unp_orb,dt[ii]*bovy_conversion.time_in_Gyr(220.,8.))
        print (pert_orb,dt[ii]*bovy_conversion.time_in_Gyr(220.,8.))
        #(R,phi,Z)
        #vR,vT,vz
        #vxvv=[R,vR,vT,z,vz,phi]
        pert_orb_RpZ= bovy_coords.rect_to_cyl(pert_orb[0],pert_orb[1],pert_orb[2])
        pert_orb_vRpZ= bovy_coords.rect_to_cyl_vec(pert_orb[3],pert_orb[4],pert_orb[5],pert_orb[0],pert_orb[1],pert_orb[2])
        pert_orb=Orbit([pert_orb_RpZ[0],pert_orb_vRpZ[0],pert_orb_vRpZ[1],pert_orb_RpZ[2],pert_orb_vRpZ[2],pert_orb_RpZ[1]])
        
        
        #forward integrate in barred potential
        pert_orb.integrate(ts_future,barpot)
        finalR[ii]= pert_orb.R(ts_future[-1])
        finalphi[ii]= pert_orb.phi(ts_future[-1])
        finalz[ii]= pert_orb.z(ts_future[-1])
        finalvR[ii]=pert_orb.vR(ts_future[-1])
        finalvT[ii]=pert_orb.vT(ts_future[-1])
        finalvz[ii]=pert_orb.vz(ts_future[-1])
        tt[ii]=dt[ii]
    
    fo.write("#R   phi   z   vR    vT    vz    ts" + "\n")
    
    for jj in range(N):
        fo.write(str(finalR[jj]) + "   " + str(finalphi[jj]) + "   " + str(finalz[jj]) + "   " + str(finalvR[jj]) + "   " + str(finalvT[jj]) + "   " + str(finalvz[jj]) + "   " + str(tt[jj]) + "\n")
        
    fo.close()
    
    return None
    



class mySCFPotential(SCFPotential):
    def _R2deriv(self,R,z,phi=0.,t=0.):
        dR= 1e-8
        return (self._Rforce(R,z,phi,t) - self._Rforce(R+dR,z,phi,t))/dR
    
    def _z2deriv(self,R,z,phi=0.,t=0.):
        dz = 1e-8
        return (self._zforce(R,z,phi,t) - self._zforce(R,z+dz,phi,t))/dz
    
    def _Rzderiv(self,R,z,phi=0.,t=0.):
        dR = 1e-8
        return (self._zforce(R,z,phi,t) - self._zforce(R+dR,z,phi,t))/dR

def Particle_Spray_MWPotentialSCFbar(mbar,Acos,Asin,rs=1.,normalize=False,pat_speed=40.,fin_phi_deg=27.,t_on=-2.,tgrow=2,tstream=5.):
    
    '''
    SCFbar starts growing at -x Gyr

    t_stream_age : age of the stream/max stripping time
    t_on: time in Gyr in the past at which the bar acquired full strength
    tgrow: no of bar periods it took the bar to grow to full strength starting at tform
            
    '''
    
    #setup the full strength bar and axisymmetric "bar"
    a=rs/ro
    omegaP=pat_speed*(ro/vo)
    
    fin_phi= np.radians(fin_phi_deg)
    
    Tbar=2.*np.pi/np.abs(omegaP) #bar period in galpy units.
    t_on=t_on/bovy_conversion.time_in_Gyr(vo,ro)
    tsteady=tgrow*Tbar
    tform = t_on - tsteady #- because past is negative
        
    mrat=mbar/10.**10. #10^10 mass of bar used to compute Acos and Asin
    
    static_bar=mySCFPotential(amp=mrat,Acos=Acos,Asin=Asin,a=a,normalize=normalize)
    
    #Note only m=0 terms are considered 
    static_axi_bar=mySCFPotential(amp=mrat,Acos=np.atleast_3d(Acos[:,:,0]),a=a)
    
    barrot=potential.SolidBodyRotationWrapperPotential(pot=static_bar,omega=omegaP,ro=ro,vo=vo,pa=fin_phi)
    
    if mbar <= 5.*10**9. :
        MWP2014SCFbar=[MWPotential2014[0],MiyamotoNagaiPotential(amp=(6.8-mrat)*10.**10*u.Msun,a=3./8.,b=0.28/8.),MWPotential2014[2],barrot]
        turn_physical_off(MWP2014SCFbar)
        #setup the corresponding axisymmetric bar
        MWP2014SCFnobar= [MWPotential2014[0],MiyamotoNagaiPotential(amp=(6.8-mrat)*10.**10*u.Msun,a=3./8.,b=0.28/8.),MWPotential2014[2],static_axi_bar]
        turn_physical_off(MWP2014SCFnobar)
        
    else : 
        MWP2014SCFbar=[MiyamotoNagaiPotential(amp=(6.8+0.5-mrat)*10.**10*u.Msun,a=3./8.,b=0.28/8.),MWPotential2014[2],barrot]
        turn_physical_off(MWP2014SCFbar)
        
        MWP2014SCFnobar= [MiyamotoNagaiPotential(amp=(6.8+0.5-mrat)*10.**10*u.Msun,a=3./8.,b=0.28/8.),MWPotential2014[2],static_axi_bar]
        turn_physical_off(MWP2014SCFnobar)
        
    
    #if t_on >= t_pal5_age, then Pal 5 sees the bar as always on
    if np.abs(t_on)*bovy_conversion.time_in_Gyr(vo,ro) >= tstream :
        return (MWP2014SCFbar,MWP2014SCFnobar)
    
    elif np.abs(tform)*bovy_conversion.time_in_Gyr(vo,ro) >= tstream:
        print ("tform > age of Pal 5 stream")
        
    elif np.abs(tform)*bovy_conversion.time_in_Gyr(vo,ro) < tstream :
           
        MWbar_grow=DehnenWrap(amp=1.,pot=MWP2014SCFbar,tform=tform,tsteady=tsteady)  
        MWaxibar_destroy=DehnenWrap(amp=-1.,pot=MWP2014SCFnobar,tform=tform,tsteady=tsteady) 

        growbarpot=[MWbar_grow,MWP2014SCFnobar,MWaxibar_destroy]

        turn_physical_off(growbarpot)
    
        return (growbarpot,MWP2014SCFnobar)
        
        
        
def sample_perturbed_pal5_new(N,barpot,nobarpot,fo='blah_trailing.dat',trailing=True,tpal5age=5.):
    
    tage=np.linspace(0.,-tpal5age,1001)/bovy_conversion.time_in_Gyr(220.,8.)
    
    if trailing :
        sdf_trailing= pal5_util.setup_pal5model(pot=nobarpot)
        R,vR,vT,z,vz,phi,dt= sdf_trailing.sample(n=N,returndt=True)
        fo=open(fo,'w')
        
    
    else :
        sdf_leading= pal5_util.setup_pal5model(pot=nobarpot,leading=True)
        R,vR,vT,z,vz,phi,dt= sdf_leading.sample(n=N,returndt=True)
        fo_lead=fo.replace('trailing','leading')
        fo=open(fo_lead,'w')
            
    #integrate Pal 5 progenitor in barpot all the way back to 5 Gyrs, 
    #from this orbits will be extracted by interpolation in the for loop
    pal5_bar= Orbit([229.018,-0.124,23.2,-2.296,-2.257,-58.7],radec=True,solarmotion=[-11.1,24.,7.25])
    pal5_bar.integrate(tage,barpot)


    #integrate Pal 5 progenitor in nobarpot all the way back to 5 Gyrs, 
    #from this orbits will be extracted by interpolation in the for loop   
    pal5_nobar= Orbit([229.018,-0.124,23.2,-2.296,-2.257,-58.7],radec=True,solarmotion=[-11.1,24.,7.25]) 
    pal5_nobar.integrate(tage,nobarpot)

    pal5_bar.turn_physical_off()
    pal5_nobar.turn_physical_off()

    finalR= numpy.empty(N)
    finalvR=numpy.empty(N)
    finalvT=numpy.empty(N)
    finalvz=numpy.empty(N)
    finalphi= numpy.empty(N)
    finalz= numpy.empty(N)
    tt=numpy.empty(N)

    for ii in range(N):

            o= Orbit([R[ii],vR[ii],vT[ii],z[ii],vz[ii],phi[ii]])
            o.turn_physical_off()
            ts= numpy.linspace(0.,-dt[ii],1001)

            o.integrate(ts,nobarpot)

            #extract the orbit at the stripping time from the above integrated orbit
            unp_orb=numpy.array([o.x(ts[-1]),o.y(ts[-1]),o.z(ts[-1]),o.vx(ts[-1]),o.vy(ts[-1]),o.vz(ts[-1])])
            pal5_orb_bar= numpy.array([pal5_bar.x(ts[-1]),pal5_bar.y(ts[-1]),pal5_bar.z(ts[-1]),pal5_bar.vx(ts[-1]),pal5_bar.vy(ts[-1]),pal5_bar.vz(ts[-1])])
            pal5_orb_nobar= numpy.array([pal5_nobar.x(ts[-1]),pal5_nobar.y(ts[-1]),pal5_nobar.z(ts[-1]),pal5_nobar.vx(ts[-1]),pal5_nobar.vy(ts[-1]),pal5_nobar.vz(ts[-1])])

            #print (unp_orb)
            #print (pal5_orb_bar)  
            #print (pal5_orb_nobar)

            #subtract Pal 5 orb in nobarpot and add Pal 5 orbit in barpot
            pert_orb= (unp_orb - pal5_orb_nobar) + pal5_orb_bar

            #print (unp_orb,dt[ii]*bovy_conversion.time_in_Gyr(220.,8.))
            #print (pert_orb,dt[ii]*bovy_conversion.time_in_Gyr(220.,8.))
            #(R,phi,Z)
            #vR,vT,vz
            #vxvv=[R,vR,vT,z,vz,phi]
            pert_orb_RpZ= bovy_coords.rect_to_cyl(pert_orb[0],pert_orb[1],pert_orb[2])
            pert_orb_vRpZ= bovy_coords.rect_to_cyl_vec(pert_orb[3],pert_orb[4],pert_orb[5],pert_orb[0],pert_orb[1],pert_orb[2])
            pert_orb=Orbit([pert_orb_RpZ[0],pert_orb_vRpZ[0],pert_orb_vRpZ[1],pert_orb_RpZ[2],pert_orb_vRpZ[2],pert_orb_RpZ[1]])

            ts_future= numpy.linspace(-dt[ii],0.,1001)
            #forward integrate in barred potential
            pert_orb.integrate(ts_future,barpot)
            finalR[ii]= pert_orb.R(ts_future[-1])
            finalphi[ii]= pert_orb.phi(ts_future[-1])
            finalz[ii]= pert_orb.z(ts_future[-1])
            finalvR[ii]=pert_orb.vR(ts_future[-1])
            finalvT[ii]=pert_orb.vT(ts_future[-1])
            finalvz[ii]=pert_orb.vz(ts_future[-1])
            tt[ii]=dt[ii]
            
    fo.write("#R   phi   z   vR    vT    vz    ts" + "\n")

    for jj in range(N):
        fo.write(str(finalR[jj]) + "   " + str(finalphi[jj]) + "   " + str(finalz[jj]) + "   " + str(finalvR[jj]) + "   " + str(finalvT[jj]) + "   " + str(finalvz[jj]) + "   " + str(tt[jj]) + "\n")
    
    fo.close()

    return None
    

def sample_streamdf_pal5_noprog(N,barpot,nobarpot,fo='blah_trailing.dat',trailing=True):
    
              
        if trailing :
            sdf_trailing= pal5_util.setup_pal5model(pot=nobarpot)
            R,vR,vT,z,vz,phi,dt= sdf_trailing.sample(n=N,returndt=True)
            fo=open(fo,'w')
          
        
        else :
            sdf_leading= pal5_util.setup_pal5model(pot=nobarpot,leading=True)
            R,vR,vT,z,vz,phi,dt= sdf_leading.sample(n=N,returndt=True)
            fo_lead=fo.replace('trailing','leading')
            fo=open(fo_lead,'w')
              
        finalR= numpy.empty(N)
        finalvR=numpy.empty(N)
        finalvT=numpy.empty(N)
        finalvz=numpy.empty(N)
        finalphi= numpy.empty(N)
        finalz= numpy.empty(N)
        tt=numpy.empty(N)

        for ii in range(N):

                o= Orbit([R[ii],vR[ii],vT[ii],z[ii],vz[ii],phi[ii]])
                o.turn_physical_off()
                ts= numpy.linspace(0.,-dt[ii],1001)

                o.integrate(ts,nobarpot)
                orb=Orbit([o.R(ts[-1]),o.vR(ts[-1]),o.vT(ts[-1]),o.z(ts[-1]),o.vz(ts[-1]),o.phi(ts[-1])])
                                
                ts_future= numpy.linspace(-dt[ii],0.,1001)
                #forward integrate in barred potential
                orb.integrate(ts_future,barpot)
                finalR[ii]= orb.R(ts_future[-1])
                finalphi[ii]= orb.phi(ts_future[-1])
                finalz[ii]= orb.z(ts_future[-1])
                finalvR[ii]=orb.vR(ts_future[-1])
                finalvT[ii]=orb.vT(ts_future[-1])
                finalvz[ii]=orb.vz(ts_future[-1])
                tt[ii]=dt[ii]
                
        fo.write("#R   phi   z   vR    vT    vz    ts" + "\n")
    
        for jj in range(N):
            fo.write(str(finalR[jj]) + "   " + str(finalphi[jj]) + "   " + str(finalz[jj]) + "   " + str(finalvR[jj]) + "   " + str(finalvT[jj]) + "   " + str(finalvz[jj]) + "   " + str(tt[jj]) + "\n")
        
        fo.close()
    
        return None
        
        
def sample_spraydf_pal5_noprog(N,barpot,nobarpot,fo='blah_trailing.dat',trailing=True):
    
        p5= Orbit([229.018,-0.124,23.2,-2.296,-2.257,-58.7],radec=True,ro=ro,vo=vo,solarmotion=[-11.1,24.,7.25])

        #convert to galpy units
        pal5=Orbit(p5._orb.vxvv)

        if trailing :
            spdft= streamspraydf.streamspraydf(50000.*u.Msun,progenitor=pal5,pot=nobarpot,leading=False,tdisrupt=5.*u.Gyr)
            RvR,dt= spdft.sample(n=N,returndt=True,integrate=False)
            R=RvR[0]
            vR=RvR[1]
            vT=RvR[2]
            z=RvR[3]
            vz=RvR[4]
            phi=RvR[5]
            
            fo=open(fo,'w')
            
     
        else :
            spdf= streamspraydf.streamspraydf(50000.*u.Msun,progenitor=pal5,pot=nobarpot,tdisrupt=5.*u.Gyr)
            RvR,dt= spdf.sample(n=N,returndt=True,integrate=False)
            R=RvR[0]
            vR=RvR[1]
            vT=RvR[2]
            z=RvR[3]
            vz=RvR[4]
            phi=RvR[5]
            fo_lead=fo.replace('trailing','leading')
            fo=open(fo_lead,'w')
              
        finalR= numpy.empty(N)
        finalvR=numpy.empty(N)
        finalvT=numpy.empty(N)
        finalvz=numpy.empty(N)
        finalphi= numpy.empty(N)
        finalz= numpy.empty(N)
        tt=numpy.empty(N)

        for ii in range(N):

                orb= Orbit([R[ii],vR[ii],vT[ii],z[ii],vz[ii],phi[ii]])
                orb.turn_physical_off()
                                                           
                ts_future= numpy.linspace(-dt[ii],0.,1001)
                #forward integrate in barred potential
                orb.integrate(ts_future,barpot)
                finalR[ii]= orb.R(ts_future[-1])
                finalphi[ii]= orb.phi(ts_future[-1])
                finalz[ii]= orb.z(ts_future[-1])
                finalvR[ii]=orb.vR(ts_future[-1])
                finalvT[ii]=orb.vT(ts_future[-1])
                finalvz[ii]=orb.vz(ts_future[-1])
                tt[ii]=dt[ii]
                
        fo.write("#R   phi   z   vR    vT    vz    ts" + "\n")
    
        for jj in range(N):
            fo.write(str(finalR[jj]) + "   " + str(finalphi[jj]) + "   " + str(finalz[jj]) + "   " + str(finalvR[jj]) + "   " + str(finalvT[jj]) + "   " + str(finalvz[jj]) + "   " + str(tt[jj]) + "\n")
        
        fo.close()
    
        return None
        
        
        
def sample_spraydf_pal5(N,barpot,fo='blah_trailing.dat',trailing=True):
    
        p5= Orbit([229.018,-0.124,23.2,-2.296,-2.257,-58.7],radec=True,ro=ro,vo=vo,solarmotion=[-11.1,24.,7.25])

        #convert to galpy units
        pal5=Orbit(p5._orb.vxvv)

        if trailing :
            spdft= streamspraydf.streamspraydf(50000.*u.Msun,progenitor=pal5,pot=barpot,leading=False,tdisrupt=5.*u.Gyr)
            RvR,dt= spdft.sample(n=N,returndt=True,integrate=True)
            R=RvR[0]
            vR=RvR[1]
            vT=RvR[2]
            z=RvR[3]
            vz=RvR[4]
            phi=RvR[5]
            
            fo=open(fo,'w')
            
     
        else :
            spdf= streamspraydf.streamspraydf(50000.*u.Msun,progenitor=pal5,pot=barpot,tdisrupt=5.*u.Gyr)
            RvR,dt= spdf.sample(n=N,returndt=True,integrate=True)
            R=RvR[0]
            vR=RvR[1]
            vT=RvR[2]
            z=RvR[3]
            vz=RvR[4]
            phi=RvR[5]
            fo_lead=fo.replace('trailing','leading')
            fo=open(fo_lead,'w')
              
                       
        fo.write("#R   phi   z   vR    vT    vz    ts" + "\n")
    
        for jj in range(N):
            fo.write(str(R[jj]) + "   " + str(phi[jj]) + "   " + str(z[jj]) + "   " + str(vR[jj]) + "   " + str(vT[jj]) + "   " + str(vz[jj]) + "   " + str(dt[jj]) + "\n")
        
        fo.close()
    
        return None
    


    
