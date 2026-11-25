import spiritedAway from "./artwork/spirited-away.webp";
import princessMononoke from "./artwork/princess-mononoke.webp";
import howlsMovingCastle from "./artwork/howls-moving-castle.webp";

// Official stills from the Studio Ghibli galleries linked in each caption.
export const films = [
  {
    title: "Spirited Away", year: 2001, image: spiritedAway,
    alt: "The lantern-lit bathhouse rises above the bridge at night.",
    position: "65% center", gallery: "chihiro", credit: "© 2001 Hayao Miyazaki/Studio Ghibli, NDDTM",
  },
  {
    title: "Princess Mononoke", year: 1997, image: princessMononoke,
    alt: "San crouches on a rooftop in a red mask and white wolf pelt.",
    position: "57% center", gallery: "mononoke", credit: "© 1997 Hayao Miyazaki/Studio Ghibli, ND",
  },
  {
    title: "Howl’s Moving Castle", searchTerm: "Moving Castle", year: 2004, image: howlsMovingCastle,
    alt: "Sophie and the scarecrow stand high above the valley at sunset.",
    position: "68% center", gallery: "howl", credit: "© 2004 Diana Wynne Jones/Hayao Miyazaki/Studio Ghibli, NDDMT",
  },
];
