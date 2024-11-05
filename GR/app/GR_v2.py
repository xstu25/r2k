import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import threading
from datetime import datetime
import time
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import traceback
import json
import re
import os
from PIL import Image
import os
import webbrowser
from datetime import datetime


class RaceDataScraper:
    def __init__(self):
        print("Initialisation du scraper...")
        self.chrome_options = Options()
        self.chrome_options.add_argument('--start-maximized')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')

        # Ajout du dictionnaire de correspondance des courses
        self.race_names = {
            "MAS": "Mascareignes",
            "GRR": "Diagonale des Fous",
            "TDB": "Trail de Bourbon",
            "MTR": "Métiss Trail",
            "ZEM": "Zembrocal"
        }

        print("Installation du ChromeDriver...")
        self.service = Service(ChromeDriverManager().install())
        self.driver = None
        self.all_data = {}
        self.load_data()

    def get_race_from_url(self, driver):
        """Récupère le code de la course depuis l'URL"""
        try:
            # Attendre que l'URL soit mise à jour avec le raceId avec un timeout plus court
            # time.sleep(1)
            current_url = driver.current_url
            print(f"URL courante: {current_url}")

            # Chercher le paramètre raceId
            match = re.search(r'raceId=(\w+)', current_url)
            if match:
                race_code = match.group(1)
                race_name = self.race_names.get(race_code, "Course inconnue")
                print(f"Course trouvée: {race_name} ({race_code})")
                return race_name
            else:
                # Si pas de raceId dans l'URL, on peut essayer de déduire la course
                # depuis les informations de la page
                try:
                    race_info = driver.find_element(By.CLASS_NAME, "mui-oah8u0").text
                    for code, name in self.race_names.items():
                        if name.lower() in race_info.lower():
                            return name
                except:
                    pass
                print("Code course non trouvé dans l'URL")
                return "Course inconnue"
        except Exception as e:
            print(f"Erreur lors de la récupération du nom de la course: {e}")
            return "Course inconnue"

    def load_data(self):
        try:
            if os.path.exists('race_data.json'):
                with open('race_data.json', 'r', encoding='utf-8') as f:
                    self.all_data = json.load(f)
                print(f"Données chargées pour {len(self.all_data)} coureurs")
        except Exception as e:
            print(f"Erreur lors du chargement des données: {e}")
            self.all_data = {}

    def save_data(self):
        try:
            with open('race_data.json', 'w', encoding='utf-8') as f:
                json.dump(self.all_data, f, ensure_ascii=False, indent=4)
            print("Données sauvegardées avec succès")
        except Exception as e:
            print(f"Erreur lors de la sauvegarde des données: {e}")

    def initialize_driver(self):
        if not self.driver:
            self.driver = webdriver.Chrome(service=self.service, options=self.chrome_options)
        return self.driver

    def close_driver(self):
        if self.driver:
            self.driver.quit()
            self.driver = None

    def extract_numeric_value(self, text):
        """Extrait la valeur numérique d'une chaîne de caractères"""
        if not text:
            return 0
        match = re.search(r'(-?\d+(?:\.\d+)?)', text.replace(',', '.'))
        return float(match.group(1)) if match else 0

    def extract_rank_info(self, element):
        """Extrait le classement et l'évolution du classement"""
        try:
            rank_text = element.find_element(By.CLASS_NAME, "mui-n2g1ua").text
            rank = int(rank_text)

            # Tenter d'extraire l'évolution du classement
            try:
                evolution_element = element.find_element(By.CLASS_NAME, "mui-1duggqj")
                evolution_text = evolution_element.text
                evolution = int(re.findall(r'[-+]?\d+', evolution_text)[0])
            except:
                evolution = 0

            return rank, evolution
        except:
            return None, None

    def get_checkpoint_data(self, driver):
        """Extraire les données des points de passage pour un coureur"""
        try:
            checkpoints = []
            rows = driver.find_elements(By.CLASS_NAME, "MuiTableRow-root")

            for row in rows:
                try:
                    cells = row.find_elements(By.CLASS_NAME, "MuiTableCell-root")
                    if len(cells) < 7:
                        continue

                    # Extraction du nom du point de passage
                    try:
                        point_name = row.find_element(By.CLASS_NAME, "mui-1v8uc0v").text.strip()
                    except:
                        continue

                    # Extraction du kilomètre
                    try:
                        km_element = row.find_elements(By.CLASS_NAME, "mui-o6szkf")[0]
                        kilometer = self.extract_numeric_value(km_element.text)
                    except:
                        kilometer = 0

                    # Extraction du temps de passage (première cellule mui-1g6ia2u)
                    try:
                        passage_time = row.find_element(By.CLASS_NAME, "mui-1g6ia2u").text.strip()
                    except:
                        passage_time = "N/A"

                    # Extraction du temps de course (modification)
                    try:
                        # Trouver toutes les cellules qui pourraient contenir le temps de course
                        time_cells = cells[4].find_elements(By.CLASS_NAME, "mui-193t7sq")
                        # Prendre le premier élément qui est directement dans la cellule
                        # (pas dans une structure imbriquée avec temps de repos)
                        race_time = None
                        for time_cell in time_cells:
                            # Vérifier si l'élément parent n'a pas la classe mui-1jkxyqi
                            # (qui est utilisée pour le temps de repos)
                            parent = time_cell.find_element(By.XPATH, "..")
                            if "mui-1jkxyqi" not in parent.get_attribute("class"):
                                race_time = time_cell.text.strip()
                                break

                        if not race_time:
                            race_time = "N/A"
                    except:
                        race_time = "N/A"

                    # Modification de l'extraction de la vitesse
                    try:
                        speed_cells = row.find_elements(By.CLASS_NAME, "mui-193t7sq")
                        speed = "N/A"
                        for cell in speed_cells:
                            cell_text = cell.text.strip()
                            if 'km/h' in cell_text:  # Vérifie si c'est bien une vitesse
                                speed = cell_text
                                break

                        # Récupération de la vitesse effort
                        effort_containers = row.find_elements(By.CLASS_NAME, "mui-1jkxyqi")
                        effort_speed = "N/A"
                        for container in effort_containers:
                            if "Vitesse effort" in container.text:
                                effort_speed_element = container.find_element(By.CLASS_NAME, "mui-vm42pa")
                                effort_speed = effort_speed_element.text.strip()
                                break
                    except Exception as e:
                        print(f"Erreur lors de l'extraction de la vitesse: {e}")
                        speed = "N/A"
                        effort_speed = "N/A"

                        # Extraction du dénivelé positif et négatif
                    try:
                        elevation_cells = row.find_elements(By.CLASS_NAME, "mui-vm42pa")
                        if len(elevation_cells) >= 2:
                            d_plus_text = elevation_cells[-2].text
                            d_minus_text = elevation_cells[-1].text

                            # Extraction des valeurs numériques sans les signes + ou -
                            d_plus = int(re.search(r'\d+', d_plus_text).group()) if re.search(r'\d+',
                                                                                              d_plus_text) else 0
                            d_minus = int(re.search(r'\d+', d_minus_text).group()) if re.search(r'\d+',
                                                                                                d_minus_text) else 0
                        else:
                            d_plus = 0
                            d_minus = 0
                    except:
                        d_plus = 0
                        d_minus = 0

                        # Extraction du classement et de son évolution
                    try:
                        rank_cells = row.find_elements(By.CLASS_NAME, "mui-ct9q29")
                        rank = None
                        evolution = None

                        for cell in rank_cells:
                            try:
                                # Extraction du classement
                                rank = cell.find_element(By.CLASS_NAME, "mui-n2g1ua").text.strip()

                                # Tentative d'extraction de l'évolution (positive ou négative)
                                try:
                                    evolution_element = None
                                    for class_name in ["mui-2e3q6l", "mui-1duggqj"]:
                                        try:
                                            evolution_element = cell.find_element(By.CLASS_NAME, class_name)
                                            break
                                        except:
                                            continue

                                    if evolution_element:
                                        evolution_text = evolution_element.text.strip()
                                        evolution_match = re.search(r'[+-]?\d+',
                                                                    evolution_text.replace('(', '').replace(')', ''))
                                        if evolution_match:
                                            evolution = int(evolution_match.group())
                                except:
                                    evolution = None
                                break
                            except:
                                continue
                    except Exception as e:
                        print(f"Erreur lors de l'extraction du classement: {e}")
                        rank = None
                        evolution = None

                    checkpoint = {
                        'point': point_name,
                        'kilometer': kilometer,
                        'passage_time': passage_time,
                        'race_time': race_time,
                        'speed': speed,
                        'effort_speed': effort_speed,
                        'elevation_gain': d_plus,
                        'elevation_loss': d_minus,
                        'rank': rank,
                        'rank_evolution': evolution
                    }
                    checkpoints.append(checkpoint)

                except Exception as e:
                    print(f"Erreur lors du traitement d'un point de passage: {e}")
                    continue

            return checkpoints

        except Exception as e:
            print(f"Erreur lors de l'extraction des points de passage: {e}")
            traceback.print_exc()
            return []

    def normalize_text(self, text):
        """Normalise le texte pour la comparaison (supprime accents et met en minuscules)"""
        import unicodedata
        return ''.join(c for c in unicodedata.normalize('NFD', text.lower())
                       if unicodedata.category(c) != 'Mn')

    def get_runner_data(self, bib_number):
        """Récupère les données complètes d'un coureur"""
        bib_str = str(bib_number)
        print(f"\nTraitement du dossard {bib_number}")

        # Vérifier si les données sont en cache
        if bib_str in self.all_data:
            print(f"Données trouvées en cache pour le dossard {bib_number}")
            return self.all_data[bib_str]

        print(f"Récupération des données en ligne pour le dossard {bib_number}")
        try:
            # Initialisation du driver et chargement de la page
            driver = self.initialize_driver()
            url = f"https://grandraid-reunion-oxybol.v3.livetrail.net/fr/2024/runners/{bib_number}"
            driver.get(url)
            time.sleep(1)

            # Initialisation des variables par défaut
            name = "Inconnu"
            category = "Inconnue"
            avg_speed = "N/A"
            state = "Inconnu"
            finish_time = "-"
            rankings = {"Général": "", "Sexe": "", "Catégorie": ""}

            # Récupération du nom de la course
            race_name = self.get_race_from_url(driver)

            # Récupération du nom du coureur
            try:
                name_element = driver.find_element(By.CLASS_NAME, "mui-oah8u0")
                name = name_element.text.strip()
            except:
                print(f"Erreur lors de la récupération du nom pour le dossard {bib_number}")

            # Récupération de la catégorie
            try:
                category_element = driver.find_element(By.CLASS_NAME, "mui-1vu7he5")
                category = category_element.text.strip()
            except:
                print(f"Erreur lors de la récupération de la catégorie pour le dossard {bib_number}")

            # Récupération de l'état et du temps
            try:
                print("Recherche de l'état du coureur...")
                raw_state = "Inconnu"

                # Chercher Finisher
                try:
                    state_container = driver.find_element(By.CLASS_NAME, "mui-w9oezj")
                    state_element = state_container.find_element(By.CSS_SELECTOR, "p.MuiTypography-noWrap")
                    raw_state = state_element.text.strip()
                    print(f"État trouvé dans mui-w9oezj: {raw_state}")
                except:
                    # Chercher Abandon ou Non partant
                    try:
                        state_container = driver.find_element(By.CLASS_NAME, "mui-gzldy9")
                        try:
                            state_element = state_container.find_element(By.CLASS_NAME, "mui-1xavr8a")
                            raw_state = state_element.text.strip()
                            print(f"État trouvé dans mui-gzldy9 (abandon): {raw_state}")
                        except:
                            state_element = state_container.find_element(By.CLASS_NAME, "mui-evvpi6")
                            raw_state = state_element.text.strip()
                            print(f"État trouvé dans mui-gzldy9 (non partant): {raw_state}")
                    except:
                        print("Aucun état trouvé dans les conteneurs connus")

                print(f"État brut trouvé: {raw_state}")
                normalized_state = raw_state.upper()

                # Traitement des non partants
                if "NON PARTANT" in normalized_state:
                    runner_data = {
                        'infos': {
                            'bib_number': bib_number,
                            'race_name': race_name,
                            'name': name,
                            'category': category,
                            'state': "Non partant",
                            'finish_time': "-",
                            'overall_rank': "-",
                            'gender_rank': "-",
                            'category_rank': "-",
                            'average_speed': "-",
                            'last_checkpoint': "-",
                            'total_elevation_gain': 0,
                            'total_elevation_loss': 0
                        },
                        'checkpoints': []
                    }
                    self.all_data[bib_str] = runner_data
                    self.save_data()
                    return runner_data

                # Détermination de l'état et du temps pour les autres cas
                if "ABANDON" in normalized_state:
                    state = "Abandon"
                elif "FINISHER" in normalized_state:
                    state = "Finisher"
                else:
                    state = "En course"

                # Récupération du temps si disponible
                if state in ["Abandon", "Finisher"]:
                    try:
                        time_element = state_container.find_element(By.CLASS_NAME, "mui-1vazesu")
                        finish_time = time_element.text.strip()
                        if ':' in finish_time:
                            hours, minutes, _ = finish_time.split(':')
                            finish_time = f"{hours}h{minutes}"
                    except:
                        finish_time = "-"
                else:
                    finish_time = "En course"

                print(f"État normalisé: {state}")

                # Récupération de la vitesse moyenne si le coureur n'est pas non partant
                try:
                    print("\nDébut extraction vitesse moyenne...")
                    main_container = driver.find_element(By.CLASS_NAME, "mui-14iziq5")
                    print("Conteneur principal trouvé")

                    info_sections = main_container.find_elements(By.CLASS_NAME, "mui-157h3i3")
                    print(f"Nombre de sections info trouvées: {len(info_sections)}")

                    if len(info_sections) >= 2:
                        info_section = info_sections[1]
                        print("Section info de vitesse trouvée, recherche des éléments...")

                        for element in info_section.find_elements(By.CLASS_NAME, "mui-8v90jo"):
                            try:
                                label_container = element.find_element(By.CLASS_NAME, "mui-ct9q29")
                                label = label_container.find_element(By.CLASS_NAME, "mui-wenrje").text.strip()
                                print(f"Label trouvé: '{label}'")

                                if "VIT. MOY." in label.upper():
                                    print("Label de vitesse moyenne trouvé!")
                                    speed_value = element.find_elements(By.TAG_NAME, "p")[-1].text.strip()
                                    print(f"Valeur de vitesse trouvée: '{speed_value}'")
                                    avg_speed = speed_value
                                    break
                            except Exception as e:
                                print(f"Erreur lors de l'analyse d'un élément: {str(e)}")
                                continue
                except Exception as e:
                    print(f"Erreur lors de la récupération de la vitesse moyenne: {str(e)}")
                    avg_speed = "N/A"

                # Récupération des classements
                print("\nDébut récupération des classements")
                try:
                    print("Recherche des containers de classement...")
                    ranking_section = driver.find_element(By.CLASS_NAME, "mui-157h3i3")
                    rank_elements = ranking_section.find_elements(By.CLASS_NAME, "mui-4ae55t")
                    print(f"Nombre d'éléments de classement trouvés: {len(rank_elements)}")

                    for element in rank_elements:
                        try:
                            type_text = element.find_element(By.CLASS_NAME, "mui-280lq").text.strip().upper()
                            value_text = element.find_element(By.CLASS_NAME, "mui-17rj2i9").text.strip()
                            print(f"Trouvé: {type_text} = {value_text}")

                            if "GÉNÉRAL" in type_text or "GENERAL" in type_text:
                                rankings["Général"] = value_text
                            elif "SEXE" in type_text:
                                rankings["Sexe"] = value_text
                            elif "CATÉGORIE" in type_text or "CATEGORIE" in type_text:
                                rankings["Catégorie"] = value_text
                        except Exception as e:
                            print(f"Erreur lors de l'extraction d'un élément de classement: {str(e)}")

                    print("État final des classements:", rankings)
                except Exception as e:
                    print(f"Erreur lors de la récupération des classements: {str(e)}")

                # Récupération des points de passage
                checkpoints = self.get_checkpoint_data(driver)

                # Détermination du dernier point
                last_checkpoint = ""
                if checkpoints:
                    last_cp = checkpoints[-1]
                    last_checkpoint = last_cp['point']

                # Construction des données du coureur
                runner_data = {
                    'infos': {
                        'bib_number': bib_number,
                        'race_name': race_name,
                        'name': name,
                        'category': category,
                        'state': state,
                        'finish_time': finish_time,
                        'overall_rank': rankings['Général'],
                        'gender_rank': rankings['Sexe'],
                        'category_rank': rankings['Catégorie'],
                        'average_speed': avg_speed,
                        'last_checkpoint': last_checkpoint,
                        'total_elevation_gain': sum(cp['elevation_gain'] for cp in checkpoints) if checkpoints else 0,
                        'total_elevation_loss': sum(cp['elevation_loss'] for cp in checkpoints) if checkpoints else 0
                    },
                    'checkpoints': checkpoints
                }

                # Sauvegarde des données
                self.all_data[bib_str] = runner_data
                self.save_data()
                return runner_data

            except Exception as e:
                print(f"Erreur lors de la récupération de l'état: {str(e)}")
                state = "Inconnu"
                finish_time = "-"
                print("État inconnu assigné suite à une erreur")
                return None

        except Exception as e:
            print(f"Erreur générale pour le dossard {bib_number}: {str(e)}")
            traceback.print_exc()
            return None

class CheckpointWindow:
    def __init__(self, parent, bib_number, runner_data, checkpoint_data):
        self.window = ctk.CTkToplevel(parent)
        self.window.title(f"Détails du coureur {bib_number}")
        self.window.state('zoomed')  # Pour Windows

        # En-tête avec les informations du coureur
        header_frame = ctk.CTkFrame(self.window)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        # Diviser l'en-tête en deux colonnes
        left_info = ctk.CTkFrame(header_frame)
        left_info.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        right_info = ctk.CTkFrame(header_frame)
        right_info.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Informations coureur - Colonne gauche
        left_info_text = (
            f"Course: {runner_data['race_name']}\n"  # Ajout de la course
            f"Dossard: {bib_number}\n"
            f"Nom: {runner_data['name']}\n"
            f"Catégorie: {runner_data['category']}\n"
            f"État: {runner_data['state']}\n"
            f"Dernier point: {runner_data['last_checkpoint']}"
        )
        ctk.CTkLabel(left_info, text=left_info_text, justify="left").pack(padx=10, pady=10)

        # Informations coureur - Colonne droite
        right_info_text = (
            f"Classement général: {runner_data['overall_rank']}\n"
            f"Classement sexe: {runner_data['gender_rank']}\n"
            f"Classement catégorie: {runner_data['category_rank']}\n"
            f"Vitesse moyenne: {runner_data['average_speed']}\n"
            f"Dénivelé: {runner_data['total_elevation_gain']}m / {runner_data['total_elevation_loss']}m"
        )

        ctk.CTkLabel(right_info, text=right_info_text, justify="left").pack(padx=10, pady=10)

        # Configuration du style du tableau
        style = ttk.Style()
        style.configure(
            "Checkpoint.Treeview",
            background="#2b2b2b",
            foreground="white",
            fieldbackground="#2b2b2b"
        )
        style.configure(
            "Checkpoint.Treeview.Heading",
            background="#2b2b2b",
            foreground="white"
        )

        # Tableau des points de passage
        tree_frame = ttk.Frame(self.window)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Tableau des points de passage
        columns = (
            "point", "kilometer", "passage_time", "race_time", "speed", "effort_speed",  # Ajout de effort_speed
            "elevation_gain", "elevation_loss", "rank", "rank_evolution"
        )

        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            style="Checkpoint.Treeview"
        )

        # Configuration des colonnes
        headers = {
            "point": "Point de passage",
            "kilometer": "KM",
            "passage_time": "Heure passage",
            "race_time": "Temps course",
            "speed": "Vitesse",
            "effort_speed": "Vitesse effort",
            "elevation_gain": "D+",
            "elevation_loss": "D-",
            "rank": "Class.",
            "rank_evolution": "Évolution"
        }

        widths = {
            "point": 250,
            "kilometer": 70,
            "passage_time": 120,
            "race_time": 120,
            "speed": 100,
            "effort_speed": 100,  # Ajout de la largeur pour effort_speed
            "elevation_gain": 80,
            "elevation_loss": 80,
            "rank": 80,
            "rank_evolution": 100
        }

        for col in columns:
            self.tree.heading(col, text=headers[col])
            self.tree.column(col, width=widths[col], anchor="center")

        # Remplir le tableau
        for checkpoint in checkpoint_data:
            elevation_gain = f"{checkpoint['elevation_gain']}m" if checkpoint['elevation_gain'] else "-"
            elevation_loss = f"{checkpoint['elevation_loss']}m" if checkpoint['elevation_loss'] else "-"

            rank_evolution = checkpoint['rank_evolution']
            if rank_evolution:
                if rank_evolution > 0:
                    evolution_text = f"+{rank_evolution}"
                else:
                    evolution_text = str(rank_evolution)
            else:
                evolution_text = "-"

            self.tree.insert('', 'end', values=(
                checkpoint['point'],
                f"{checkpoint['kilometer']:.1f}",
                checkpoint['passage_time'],
                checkpoint['race_time'],
                checkpoint['speed'],
                checkpoint['effort_speed'],
                elevation_gain,
                elevation_loss,
                checkpoint['rank'] if checkpoint['rank'] else "-",
                evolution_text
            ))

        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(fill=tk.BOTH, expand=True)


class RaceTrackerApp:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("Suivi Grand Raid")
        # Maximiser la fenêtre
        self.root.state('zoomed')

        style = ttk.Style()
        style.theme_use('default')
        style.configure(
            "Treeview",
            background="#2b2b2b",
            foreground="white",
            rowheight=25,
            fieldbackground="#2b2b2b"
        )
        style.configure(
            "Treeview.Heading",
            background="#2b2b2b",
            foreground="white",
            relief="flat"
        )
        style.map("Treeview", background=[('selected', '#22559b')])

        self.scraper = RaceDataScraper()
        self.checkpoint_windows = {}
        self.initial_data = []  # Pour stocker les données initiales
        self.current_filters = {
            'race': "Toutes les courses",
            'state': "Tous les états",
            'category': "Toutes les catégories"
        }
        self.create_widgets()
        self.load_cached_data()

    def create_export_button(self):
        """Créer le bouton d'export avec une image"""
        export_frame = ctk.CTkFrame(self.input_frame)  # Maintenant self.input_frame existe
        export_frame.pack(side=tk.LEFT, padx=20)

        try:
            image = Image.open("dl.png")
            image = image.resize((20, 20))
            photo = ctk.CTkImage(light_image=image, dark_image=image, size=(20, 20))
            self.export_button = ctk.CTkButton(
                export_frame,
                text="Exporter HTML",
                image=photo,
                compound="left",
                command=self.export_to_html
            )
        except Exception as e:
            print(f"Erreur lors du chargement de l'image: {e}")
            # Fallback si l'image n'est pas trouvée
            self.export_button = ctk.CTkButton(
                export_frame,
                text="Exporter HTML",
                command=self.export_to_html
            )

        self.export_button.pack(side=tk.LEFT)

    def export_to_html(self):
        """Export complet des données"""
        try:
            # Timestamp pour le nom du dossier principal
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_dir = f"export{timestamp}"

            # Créer les dossiers
            os.makedirs(export_dir)
            os.makedirs(os.path.join(export_dir, "coureurs"))
            os.makedirs(os.path.join(export_dir, "analyses"))

            # Exporter le tableau principal (index.html)
            main_table_html = self.create_main_table_html(timestamp)
            with open(os.path.join(export_dir, "index.html"), "w", encoding="utf-8") as f:
                f.write(main_table_html)

            # Exporter les détails des coureurs - Ajout du timestamp ici
            for bib in self.scraper.all_data:
                runner_html = self.create_runner_table_html(bib, timestamp)  # Ajout du timestamp ici
                if runner_html:  # Vérifier si le HTML a été généré
                    runner_file = os.path.join(export_dir, "coureurs", f"coureur_{bib}.html")
                    with open(runner_file, "w", encoding="utf-8") as f:
                        f.write(runner_html)

            # Créer une instance temporaire de TopAnalysisWindow pour l'export des analyses
            top_analysis = TopAnalysisWindow(self.root, self.scraper, list(self.scraper.all_data.keys()))

            # Récupérer la liste des courses
            courses = ["Toutes les courses"] + sorted(list(set(
                data['infos']['race_name']
                for bib in self.scraper.all_data.keys()
                for data in [self.scraper.all_data[str(bib)]]
            )))

            # Créer le dossier analyses
            analyses_dir = os.path.join(export_dir, "analyses")

            # Exporter les analyses pour chaque course
            for course in courses:
                # Progression
                top_analysis.export_progression_analysis(analyses_dir, course)
                # Dénivelés
                top_analysis.export_elevation_analysis(analyses_dir, course)
                # Vitesses
                top_analysis.export_speed_analysis(analyses_dir, course)

            # Exporter l'analyse des sections
            top_analysis.export_section_analysis(analyses_dir)

            # Créer l'index des analyses
            index_html = top_analysis.create_analyses_index_html(courses)
            with open(os.path.join(analyses_dir, "index.html"), "w", encoding="utf-8") as f:
                f.write(index_html)

            # Fermer la fenêtre temporaire
            top_analysis.window.destroy()

            # Ouvrir le fichier index dans le navigateur
            webbrowser.open(f"file://{os.path.abspath(os.path.join(export_dir, 'index.html'))}")

            messagebox.showinfo(
                "Export réussi",
                f"Les fichiers ont été exportés dans le dossier:\n{export_dir}"
            )

        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de l'export: {str(e)}")
            traceback.print_exc()

    def export_top_analyses(self, export_dir):
        """Exporter toutes les analyses TOP"""
        try:
            analyses_dir = os.path.join(export_dir, "analyses")
            os.makedirs(analyses_dir, exist_ok=True)

            # Créer une instance de TopAnalysisWindow temporaire pour accéder aux données
            top_analysis = TopAnalysisWindow(self.root, self.scraper, [bib for bib in self.scraper.all_data.keys()])

            # Récupérer la liste des courses disponibles
            courses = ["Toutes les courses"] + sorted(list(set(
                data['infos']['race_name']
                for bib in self.scraper.all_data.keys()
                for data in [self.scraper.all_data[str(bib)]]
            )))

            # Exporter les analyses pour chaque course
            for course in courses:
                # Mettre à jour la sélection de course
                top_analysis.race_selector.set(course)

                # 1. Progression
                # Progression globale
                data = top_analysis.get_progression_global_data(selected_race)
                html = top_analysis.create_analysis_table_html(
                    "Progression globale",
                    ["Position", "Dossard", "Nom", "Course", "Pos. départ", "Pos. finale", "Progression"],
                    data,
                    course
                )
                with open(os.path.join(analyses_dir,
                                       f"progression_globale{'_' + course.lower().replace(' ', '_') if course != 'Toutes les courses' else ''}.html"),
                          "w", encoding="utf-8") as f:
                    f.write(html)

                # Progression sections
                data = top_analysis.get_progression_sections_data()
                html = top_analysis.create_analysis_table_html(
                    "Progression entre points",
                    ["Position", "Dossard", "Nom", "Course", "Section", "Progression", "Classements"],
                    data,
                    course
                )
                with open(os.path.join(analyses_dir,
                                       f"progression_sections{'_' + course.lower().replace(' ', '_') if course != 'Toutes les courses' else ''}.html"),
                          "w", encoding="utf-8") as f:
                    f.write(html)

                # 2. Dénivelés
                # Grimpeurs
                data = top_analysis.get_climbers_data()
                html = top_analysis.create_analysis_table_html(
                    "Top Grimpeurs",
                    ["Position", "Dossard", "Nom", "Course", "D+ total", "Temps", "Vitesse", "Pente moy.", "Tendance"],
                    data,
                    course
                )
                with open(os.path.join(analyses_dir,
                                       f"grimpeurs{'_' + course.lower().replace(' ', '_') if course != 'Toutes les courses' else ''}.html"),
                          "w", encoding="utf-8") as f:
                    f.write(html)

                # Descendeurs
                data = top_analysis.get_descenders_data()
                html = top_analysis.create_analysis_table_html(
                    "Top Descendeurs",
                    ["Position", "Dossard", "Nom", "Course", "D- total", "Temps", "Vitesse", "Pente moy.", "Tendance"],
                    data,
                    course
                )
                with open(os.path.join(analyses_dir,
                                       f"descendeurs{'_' + course.lower().replace(' ', '_') if course != 'Toutes les courses' else ''}.html"),
                          "w", encoding="utf-8") as f:
                    f.write(html)

                # 3. Vitesses
                # Vitesse moyenne
                data = top_analysis.get_speed_avg_data()
                html = top_analysis.create_analysis_table_html(
                    "Vitesse moyenne",
                    ["Position", "Dossard", "Nom", "Course", "Vitesse moyenne"],
                    data,
                    course
                )
                with open(os.path.join(analyses_dir,
                                       f"vitesse_moyenne{'_' + course.lower().replace(' ', '_') if course != 'Toutes les courses' else ''}.html"),
                          "w", encoding="utf-8") as f:
                    f.write(html)

                # Vitesse effort
                data = top_analysis.get_speed_effort_data()
                html = top_analysis.create_analysis_table_html(
                    "Vitesse effort",
                    ["Position", "Dossard", "Nom", "Course", "Vitesse effort"],
                    data,
                    course
                )
                with open(os.path.join(analyses_dir,
                                       f"vitesse_effort{'_' + course.lower().replace(' ', '_') if course != 'Toutes les courses' else ''}.html"),
                          "w", encoding="utf-8") as f:
                    f.write(html)

                # Vitesse sections
                data = top_analysis.get_speed_sections_data()
                html = top_analysis.create_analysis_table_html(
                    "Vitesse par section",
                    ["Position", "Dossard", "Nom", "Course", "Section", "Distance", "Vitesse"],
                    data,
                    course
                )
                with open(os.path.join(analyses_dir,
                                       f"vitesse_sections{'_' + course.lower().replace(' ', '_') if course != 'Toutes les courses' else ''}.html"),
                          "w", encoding="utf-8") as f:
                    f.write(html)

            # Créer la page d'index des analyses
            index_html = self.create_analyses_index_html(courses)
            with open(os.path.join(analyses_dir, "index.html"), "w", encoding="utf-8") as f:
                f.write(index_html)

            # Ajouter le lien vers les analyses dans le menu principal
            self.add_analyses_link_to_main_menu(export_dir)

            # Ajouter l'export des sections
            html = top_analysis.create_section_analysis_html()
            with open(os.path.join(analyses_dir, "analyse_sections.html"), "w", encoding="utf-8") as f:
                f.write(html)

        except Exception as e:
            print(f"Erreur lors de l'export des analyses TOP: {str(e)}")
            traceback.print_exc()
        finally:
            if 'top_analysis' in locals():
                if hasattr(top_analysis, 'window'):
                    top_analysis.window.destroy()

    def create_analyses_index_html(self, courses):
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Analyses TOP</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                .analysis-section {
                    margin-bottom: 30px;
                }
                .analysis-links {
                    list-style: none;
                    padding-left: 20px;
                }
            </style>
        </head>
        <body>
            <div class="container mt-4">
                <h1>Analyses TOP</h1>
                <div class="mb-4">
                    <a href="../index.html" class="btn btn-secondary">← Retour au tableau des coureurs</a>
                </div>

                <div class="row">
                    <div class="col-md-4">
                        <div class="analysis-section">
                            <h3>Progression</h3>
                            <ul class="analysis-links">
                                <li><a href="progression_globale.html">Progression globale</a></li>
                                <li><a href="progression_sections.html">Progression entre points</a></li>
                            </ul>
                        </div>
                    </div>

                    <div class="col-md-4">
                        <div class="analysis-section">
                            <h3>Dénivelés</h3>
                            <ul class="analysis-links">
                                <li><a href="grimpeurs.html">Top Grimpeurs</a></li>
                                <li><a href="descendeurs.html">Top Descendeurs</a></li>
                            </ul>
                        </div>
                    </div>

                    <div class="col-md-4">
                        <div class="analysis-section">
                            <h3>Vitesses</h3>
                            <ul class="analysis-links">
                                <li><a href="vitesse_moyenne.html">Vitesse moyenne</a></li>
                                <li><a href="vitesse_effort.html">Vitesse effort</a></li>
                                <li><a href="vitesse_sections.html">Vitesse par section</a></li>
                            </ul>
                        </div>
                    </div>
                </div>

                <div class="row">
                    <div class="col-md-12">
                        <div class="analysis-section">
                            <h3>Sections</h3>
                            <ul class="analysis-links">
                                <li><a href="analyse_sections.html">Analyse par section</a></li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        return html

    def add_analyses_link_to_main_menu(self, export_dir):
        """Ajouter un lien vers les analyses dans le menu principal"""
        with open(os.path.join(export_dir, "index.html"), "r", encoding="utf-8") as f:
            content = f.read()

        # Ajouter le lien vers les analyses avant la fermeture du container
        analyses_link = """
            <div class="row mt-3">
                <div class="col">
                    <a href="analyses/index.html" class="btn btn-primary">Voir les analyses TOP →</a>
                </div>
            </div>
        """
        content = content.replace('</div>\n    </body>', f'{analyses_link}\n        </div>\n    </body>')

        with open(os.path.join(export_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(content)

    def create_main_table_html(self, timestamp):
        """Créer le HTML pour le tableau principal avec tri et liens vers les détails"""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Tableau des coureurs</title>
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css">
            <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
            <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.10.24/css/dataTables.bootstrap5.min.css">
            <script type="text/javascript" src="https://cdn.datatables.net/1.10.24/js/jquery.dataTables.min.js"></script>
            <script type="text/javascript" src="https://cdn.datatables.net/1.10.24/js/dataTables.bootstrap5.min.js"></script>
            <style>
                .runner-link {
                    text-decoration: none;
                    color: inherit;
                }
                .runner-link:hover {
                    text-decoration: underline;
                    color: #0056b3;
                }
            </style>
        </head>
        <body>
            <div class="container-fluid mt-3">
                <div class="row mb-3">
                    <div class="col">
                        <h3>Tableau des coureurs</h3>
                        <p class="text-muted">Cliquez sur un dossard pour voir les détails du coureur</p>
                    </div>
                </div>
                <div class="row mb-3">
                    <div class="col">
                        <a href="analyses/index.html" class="btn btn-primary">Voir les Analyses TOP →</a>
                    </div>
                </div>
                <table id="mainTable" class="table table-striped table-bordered">
                    <thead>
                        <tr>
        """

        # Ajouter les en-têtes de colonnes
        for col in ["Course", "Dossard", "Nom", "Catégorie", "Class. Général", "Class. Sexe",
                    "Class. Catégorie", "Vitesse moy.", "État", "Dernier Point", "Temps",
                    "D+ Total", "D- Total"]:
            html += f"<th>{col}</th>"

        html += """
                        </tr>
                    </thead>
                    <tbody>
        """

        # Ajouter les données avec liens vers les détails des coureurs
        for item in self.tree.get_children():
            values = self.tree.item(item)["values"]
            if values:
                html += "<tr>"
                for i, value in enumerate(values):
                    if i == 1:  # Colonne du dossard
                        html += f'<td><a href="coureurs/coureur_{value}.html" class="runner-link" target="_blank">{value}</a></td>'
                    else:
                        html += f"<td>{value}</td>"
                html += "</tr>"

        html += """
                    </tbody>
                </table>
            </div>
            <script>
                $(document).ready(function() {
                    $('#mainTable').DataTable({
                        "pageLength": 50,
                        "language": {
                            "url": "//cdn.datatables.net/plug-ins/1.10.24/i18n/French.json"
                        },
                        "order": [[1, "asc"]]
                    });
                });
            </script>
        </body>
        </html>
        """
        return html

    def create_runner_table_html(self, bib, timestamp):
        """Créer le HTML pour le tableau détaillé d'un coureur avec lien retour"""
        if bib not in self.scraper.all_data:
            return None

        # Récupérer les données du coureur
        runner_data = self.scraper.all_data[bib]

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Détails coureur {bib}</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                .positive-evolution {{ color: #28a745; }}
                .negative-evolution {{ color: #dc3545; }}
                .neutral-evolution {{ color: #6c757d; }}
            </style>
        </head>
        <body>
            <div class="container-fluid mt-3">
                <div class="row mb-3">
                    <div class="col">
                        <a href="../index.html" class="btn btn-secondary mb-3">← Retour au tableau principal</a>
                        <h3>Détails du coureur {bib}</h3>
                    </div>
                </div>
                <div class="row mb-4">
                    <div class="col">
                        <h4>Informations coureur</h4>
                        <table class="table table-bordered">
                            <tr>
                                <th class="bg-light" style="width: 25%">Course</th>
                                <td style="width: 25%">{runner_data['infos']['race_name']}</td>
                                <th class="bg-light" style="width: 25%">Dossard</th>
                                <td style="width: 25%">{bib}</td>
                            </tr>
                            <tr>
                                <th class="bg-light">Nom</th>
                                <td>{runner_data['infos']['name']}</td>
                                <th class="bg-light">Catégorie</th>
                                <td>{runner_data['infos']['category']}</td>
                            </tr>
                            <tr>
                                <th class="bg-light">État</th>
                                <td>{runner_data['infos']['state']}</td>
                                <th class="bg-light">Temps</th>
                                <td>{runner_data['infos']['finish_time']}</td>
                            </tr>
                            <tr>
                                <th class="bg-light">Class. Général</th>
                                <td>{runner_data['infos']['overall_rank']}</td>
                                <th class="bg-light">Class. Sexe</th>
                                <td>{runner_data['infos']['gender_rank']}</td>
                            </tr>
                            <tr>
                                <th class="bg-light">D+ Total</th>
                                <td>{runner_data['infos']['total_elevation_gain']}m</td>
                                <th class="bg-light">D- Total</th>
                                <td>{runner_data['infos']['total_elevation_loss']}m</td>
                            </tr>
                        </table>
                    </div>
                </div>
        """

        # Checkpoints section
        if 'checkpoints' in runner_data and runner_data['checkpoints']:
            html += """
                <div class="row">
                    <div class="col">
                        <h4>Points de passage</h4>
                        <table class="table table-striped table-bordered">
                            <thead class="table-light">
                                <tr>
                                    <th>Point</th>
                                    <th>KM</th>
                                    <th>Heure passage</th>
                                    <th>Temps course</th>
                                    <th>Vitesse</th>
                                    <th>Vitesse effort</th>
                                    <th>D+</th>
                                    <th>D-</th>
                                    <th>Class.</th>
                                    <th>Évolution</th>
                                </tr>
                            </thead>
                            <tbody>
            """

            for cp in runner_data['checkpoints']:
                # Traitement de l'évolution du classement
                evolution = cp.get('rank_evolution')
                if evolution is not None:
                    if evolution > 0:
                        evolution_text = f'<span class="positive-evolution">+{evolution}</span>'
                    elif evolution < 0:
                        evolution_text = f'<span class="negative-evolution">{evolution}</span>'
                    else:
                        evolution_text = f'<span class="neutral-evolution">{evolution}</span>'
                else:
                    evolution_text = '-'

                # Formatage des valeurs
                kilometer = f"{cp.get('kilometer', 0):.1f}" if cp.get('kilometer') is not None else "-"
                elevation_gain = f"{cp.get('elevation_gain', 0)}m" if cp.get('elevation_gain') is not None else "-"
                elevation_loss = f"{cp.get('elevation_loss', 0)}m" if cp.get('elevation_loss') is not None else "-"

                html += f"""
                    <tr>
                        <td>{cp.get('point', '-')}</td>
                        <td>{kilometer}</td>
                        <td>{cp.get('passage_time', '-')}</td>
                        <td>{cp.get('race_time', '-')}</td>
                        <td>{cp.get('speed', '-')}</td>
                        <td>{cp.get('effort_speed', '-')}</td>
                        <td>{elevation_gain}</td>
                        <td>{elevation_loss}</td>
                        <td>{cp.get('rank', '-')}</td>
                        <td>{evolution_text}</td>
                    </tr>
                """

            html += """
                            </tbody>
                        </table>
                    </div>
                </div>
            """
        else:
            html += """
                <div class="row">
                    <div class="col">
                        <div class="alert alert-info" role="alert">
                            Aucun point de passage disponible pour ce coureur.
                        </div>
                    </div>
                </div>
            """

        # Fermeture des balises
        html += """
                </div>
            </body>
            </html>
        """

        return html

    def create_widgets(self):
        self.main_frame = ctk.CTkFrame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Frame de saisie
        self.input_frame = ctk.CTkFrame(self.main_frame)
        self.input_frame.pack(fill=tk.X, padx=10, pady=10)

        ctk.CTkLabel(self.input_frame, text="Numéros de dossard (séparés par des virgules):").pack(side=tk.LEFT, padx=5)
        self.bib_entry = ctk.CTkEntry(self.input_frame, width=400)
        self.bib_entry.pack(side=tk.LEFT, padx=5)

        self.scan_button = ctk.CTkButton(self.input_frame, text="Scanner", command=self.start_scanning)
        self.scan_button.pack(side=tk.LEFT, padx=5)

        # Frame de progression
        progress_frame = ctk.CTkFrame(self.main_frame)
        progress_frame.pack(fill=tk.X, padx=10, pady=5)
        self.progress_label = ctk.CTkLabel(progress_frame, text="")
        self.progress_label.pack(side=tk.LEFT, padx=5)

        # Configuration du tableau principal
        columns = (
            "race_name", "bib", "name", "category", "overall_rank", "gender_rank",
            "category_rank", "average_speed", "state", "last_checkpoint",
            "finish_time", "total_elevation_gain", "total_elevation_loss"
        )

        tree_frame = ttk.Frame(self.main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings"
        )

        # Configuration des colonnes
        headers = {
            "race_name": "Course",  # Ajout de l'en-tête pour la course
            "bib": "Dossard",
            "name": "Nom",
            "category": "Catégorie",
            "overall_rank": "Class. Général",
            "gender_rank": "Class. Sexe",
            "category_rank": "Class. Catégorie",
            "average_speed": "Vitesse moy.",
            "state": "État",
            "last_checkpoint": "Dernier Point",
            "finish_time": "Temps",
            "total_elevation_gain": "D+ Total",
            "total_elevation_loss": "D- Total"
        }

        widths = {
            "race_name": 150,  # Ajout de la largeur pour la colonne course
            "bib": 80,
            "name": 200,
            "category": 100,
            "overall_rank": 100,
            "gender_rank": 100,
            "category_rank": 120,
            "average_speed": 100,
            "state": 100,
            "last_checkpoint": 200,
            "finish_time": 100,
            "total_elevation_gain": 100,
            "total_elevation_loss": 100
        }

        for col in columns:
            self.tree.heading(
                col,
                text=headers[col],
                command=lambda c=col: self.treeview_sort_column(c, False)
            )
            self.tree.column(col, width=widths[col], anchor="center")

        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(fill=tk.BOTH, expand=True)

        self.tree.bind('<Double-1>', self.show_checkpoint_details)

        # Frame pour les filtres
        filter_frame = ctk.CTkFrame(self.main_frame)
        filter_frame.pack(fill=tk.X, padx=10, pady=5)

        ctk.CTkLabel(filter_frame, text="Filtres:").pack(side=tk.LEFT, padx=5)

        # Créer les widgets de filtre avec les nouveaux callbacks
        self.race_filter = ctk.CTkComboBox(
            filter_frame,
            values=["Toutes les courses"],
            command=lambda x: self.on_filter_change('race', x)
        )
        self.race_filter.pack(side=tk.LEFT, padx=5)
        self.race_filter.set("Toutes les courses")

        self.state_filter = ctk.CTkComboBox(
            filter_frame,
            values=["Tous les états"],
            command=lambda x: self.on_filter_change('state', x)
        )
        self.state_filter.pack(side=tk.LEFT, padx=5)
        self.state_filter.set("Tous les états")

        self.category_filter = ctk.CTkComboBox(
            filter_frame,
            values=["Toutes les catégories"],
            command=lambda x: self.on_filter_change('category', x)
        )
        self.category_filter.pack(side=tk.LEFT, padx=5)
        self.category_filter.set("Toutes les catégories")

        # Ajouter un bouton de réinitialisation
        self.reset_filters_button = ctk.CTkButton(
            filter_frame,
            text="Réinitialiser les filtres",
            command=self.reset_filters
        )
        self.reset_filters_button.pack(side=tk.LEFT, padx=20)

        # Ajouter le bouton TOP Analyses dans self.input_frame
        self.analysis_button = ctk.CTkButton(
            self.input_frame,  # Utiliser self.input_frame ici
            text="TOP Analyses",
            command=self.show_top_analysis
        )
        self.analysis_button.pack(side=tk.LEFT, padx=5)

        # Ajouter le bouton d'export
        self.create_export_button()

    def load_initial_data(self):
        """Charger et stocker les données initiales"""
        self.initial_data.clear()
        for item in self.tree.get_children():
            self.initial_data.append(self.tree.item(item))

    def on_filter_change(self, filter_type, value):
        """Gestion du changement de filtre avec type de filtre"""
        print(f"Changement du filtre {filter_type}: {value}")
        self.current_filters[filter_type] = value
        self.apply_filters()

    def reset_filters(self):
        """Réinitialiser tous les filtres et restaurer les données initiales"""
        # Réinitialiser les valeurs des filtres
        self.race_filter.set("Toutes les courses")
        self.state_filter.set("Tous les états")
        self.category_filter.set("Toutes les catégories")

        self.current_filters = {
            'race': "Toutes les courses",
            'state': "Tous les états",
            'category': "Toutes les catégories"
        }

        # Effacer le tableau actuel
        self.tree.delete(*self.tree.get_children())

        # Restaurer les données initiales
        for item_data in self.initial_data:
            self.tree.insert('', 'end', values=item_data['values'], tags=item_data.get('tags', ()))

        print("Filtres réinitialisés - Données restaurées à l'état initial")
        print(f"Nombre total de coureurs: {len(self.initial_data)}")

    def load_cached_data(self):
        """Charger les données en cache et initialiser les données de référence"""
        if self.scraper.all_data:
            cached_bibs = list(self.scraper.all_data.keys())
            print(f"Chargement automatique de {len(cached_bibs)} dossards")
            for bib in cached_bibs:
                data = self.scraper.all_data[bib]
                self.add_runner_to_tree(data)

            # Stocker les données initiales après le chargement
            self.load_initial_data()

            self.update_filters()
            self.progress_label.configure(text=f"{len(cached_bibs)} dossards chargés depuis le cache")

    def show_top_analysis(self):
        # Récupérer tous les dossards actuellement affichés dans le tableau
        bibs = []
        for item in self.tree.get_children():
            values = self.tree.item(item)['values']
            if values:
                bibs.append(values[1])  # L'index 1 correspond à la colonne du dossard

        if not bibs:
            messagebox.showwarning(
                "Attention",
                "Aucun coureur n'est actuellement affiché dans le tableau!"
            )
            return

        # Créer la fenêtre d'analyse
        TopAnalysisWindow(self.root, self.scraper, bibs)

    def scanning_complete(self, scanned, cached):
        """Finalise le processus de scan"""
        self.scan_button.configure(state="normal")
        if scanned + cached > 0:
            self.progress_label.configure(
                text=f"Scan terminé ! ({cached} depuis le cache, {scanned} nouveaux scans)"
            )
        else:
            self.progress_label.configure(text="Scan terminé !")

    def show_checkpoint_details(self, event):
        """Affiche la fenêtre des détails pour un coureur"""
        selection = self.tree.selection()
        if not selection:
            return

        item = selection[0]
        values = self.tree.item(item)['values']
        if not values:
            return

        bib_number = str(values[1])  # Le dossard est maintenant la deuxième colonne (index 1)

        if bib_number in self.scraper.all_data:
            # Créer une nouvelle fenêtre ou mettre à jour l'existante
            if bib_number in self.checkpoint_windows:
                self.checkpoint_windows[bib_number].window.destroy()

            # Récupérer les données du coureur
            runner_data = self.scraper.all_data[bib_number]['infos']

            # Créer la nouvelle fenêtre
            self.checkpoint_windows[bib_number] = CheckpointWindow(
                self.root,
                bib_number,
                runner_data,
                self.scraper.all_data[bib_number]['checkpoints']
            )
        else:
            messagebox.showwarning(
                "Données non disponibles",
                f"Pas de données de points de passage pour le dossard {bib_number}"
            )

    def treeview_sort_column(self, col, reverse):
        """Trie le tableau selon une colonne avec gestion correcte des nombres"""
        try:
            data = [(self.tree.set(item, col), item) for item in self.tree.get_children('')]

            def convert_to_number(value):
                """Convertit une valeur en nombre en gérant les cas spéciaux"""
                if not value or value.strip() == '-':
                    return float('inf')  # Mettre les valeurs vides à la fin
                try:
                    # Nettoyer la valeur et convertir en nombre
                    clean_value = ''.join(c for c in value if c.isdigit() or c == '.')
                    return float(clean_value) if '.' in clean_value else int(clean_value)
                except:
                    return value

            # Détermine si la colonne doit être triée numériquement
            numeric_columns = {
                "overall_rank", "gender_rank", "category_rank",  # Classements
                "bib",  # Dossards
                "total_elevation_gain", "total_elevation_loss"  # Dénivelés
            }

            # Tri avec gestion spéciale pour les colonnes numériques
            if col in numeric_columns:
                data.sort(
                    key=lambda x: convert_to_number(x[0]),
                    reverse=reverse
                )
            else:
                # Tri normal pour les autres colonnes
                data.sort(
                    key=lambda x: x[0].lower() if isinstance(x[0], str) else x[0],
                    reverse=reverse
                )

            # Réorganiser les items
            for idx, (val, item) in enumerate(data):
                self.tree.move(item, '', idx)

            # Inverser le sens pour le prochain clic
            self.tree.heading(
                col,
                text=self.tree.heading(col)['text'],
                command=lambda: self.treeview_sort_column(col, not reverse)
            )

        except Exception as e:
            print(f"Erreur lors du tri de la colonne {col}: {e}")
            traceback.print_exc()


    def add_runner_to_tree(self, data):
        """Ajoute un coureur au tableau principal avec toutes les nouvelles données"""
        if data and 'infos' in data:
            info = data['infos']
            self.tree.insert('', 'end', values=(
                info['race_name'],  # Ajout du nom de la course
                info['bib_number'],
                info['name'],
                info['category'],
                info['overall_rank'],
                info['gender_rank'],
                info['category_rank'],
                info['average_speed'],
                info['state'],
                info['last_checkpoint'],
                info['finish_time'],
                f"{info['total_elevation_gain']}m",
                f"{info['total_elevation_loss']}m"
            ))

    def update_filters(self):
        """Mise à jour des listes de filtres en fonction des données actuelles"""
        categories = set()
        states = set()
        races = set()
        races.add("Toutes les courses")
        states.add("Tous les états")
        categories.add("Toutes les catégories")

        for item in self.tree.get_children():
            values = self.tree.item(item)['values']
            if values:
                races.add(values[0])  # Course (index 0)
                categories.add(values[3])  # Catégorie (index 3)
                states.add(values[8])  # État (index 8)

        # Mettre à jour les valeurs des ComboBox
        self.race_filter.configure(values=sorted(list(races)))
        self.state_filter.configure(values=sorted(list(states)))
        self.category_filter.configure(values=sorted(list(categories)))



    def apply_filters(self):
        """Application des filtres avec gestion améliorée"""
        # Sauvegarder toutes les lignes originales
        all_items = [(self.tree.item(item), item) for item in self.tree.get_children()]

        # Effacer l'affichage actuel
        self.tree.delete(*self.tree.get_children())

        filtered_count = 0

        for item_data, item_id in all_items:
            values = item_data['values']
            if not values:
                continue

            show_item = True

            # Vérifier chaque filtre
            if self.current_filters['race'] != "Toutes les courses" and values[0] != self.current_filters['race']:
                show_item = False
            if self.current_filters['category'] != "Toutes les catégories" and values[3] != self.current_filters[
                'category']:
                show_item = False
            if self.current_filters['state'] != "Tous les états" and values[8] != self.current_filters['state']:
                show_item = False

            if show_item:
                self.tree.insert('', 'end', values=values, tags=item_data.get('tags', ()))
                filtered_count += 1

        # Afficher un résumé des filtres appliqués
        filter_summary = []
        if self.current_filters['race'] != "Toutes les courses":
            filter_summary.append(f"Course: {self.current_filters['race']}")
        if self.current_filters['category'] != "Toutes les catégories":
            filter_summary.append(f"Catégorie: {self.current_filters['category']}")
        if self.current_filters['state'] != "Tous les états":
            filter_summary.append(f"État: {self.current_filters['state']}")

        print(f"Filtres actifs: {' | '.join(filter_summary) if filter_summary else 'Aucun'}")
        print(f"Nombre de coureurs affichés: {filtered_count}")


    def scan_bibs(self, bib_numbers):
        total = len(bib_numbers)
        scanned = 0
        cached = 0

        for i, bib in enumerate(bib_numbers, 1):
            bib_str = str(bib)
            if bib_str in self.scraper.all_data:
                self.progress_label.configure(
                    text=f"Récupération du cache pour le dossard {bib} ({i}/{total})..."
                )
                data = self.scraper.all_data[bib_str]
                cached += 1
            else:
                self.progress_label.configure(
                    text=f"Scan du dossard {bib} ({i}/{total})..."
                )
                data = self.scraper.get_runner_data(bib)
                scanned += 1

            if data:
                self.root.after(0, self.add_runner_to_tree, data)
            # time.sleep(1)

        self.root.after(0, lambda: self.scanning_complete(scanned, cached))
        self.root.after(0, self.update_filters)

    def start_scanning(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        bib_text = self.bib_entry.get().strip()
        if not bib_text:
            messagebox.showwarning("Attention", "Veuillez entrer des numéros de dossard!")
            return

        try:
            bib_numbers = [int(x.strip()) for x in bib_text.split(',')]
        except ValueError:
            messagebox.showerror("Erreur", "Format de numéro de dossard invalide!")
            return

        self.scan_button.configure(state="disabled")
        thread = threading.Thread(target=self.scan_bibs, args=(bib_numbers,))
        thread.daemon = True
        thread.start()

    def run(self):
        self.root.mainloop()

    def __del__(self):
        if hasattr(self, 'scraper'):
            self.scraper.close_driver()


class TopAnalysisWindow:
    def __init__(self, parent, scraper, bibs):
        self.window = ctk.CTkToplevel(parent)
        self.window.title("TOP Analyses")
        self.window.geometry("1400x800")
        self.scraper = scraper
        self.bibs = bibs
        self.sections_info = {}  # Initialisation de sections_info ici

        # Frame principal avec défilement
        self.main_frame = ctk.CTkFrame(self.window)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Frame pour les filtres en haut²
        self.filter_frame = ctk.CTkFrame(self.main_frame)
        self.filter_frame.pack(fill=tk.X, padx=5, pady=5)

        # Sélecteur de course
        ctk.CTkLabel(self.filter_frame, text="Course:").pack(side=tk.LEFT, padx=5)
        self.race_values = self.get_unique_races()
        self.race_selector = ctk.CTkComboBox(
            self.filter_frame,
            values=self.race_values,
            command=self.on_race_selected
        )
        self.race_selector.pack(side=tk.LEFT, padx=5)
        self.race_selector.set("Toutes les courses")

        # Sélecteur de section (visible uniquement pour l'onglet sections)
        self.section_frame = ctk.CTkFrame(self.filter_frame)
        self.section_selector = None



        # Créer les onglets
        self.tabview = ctk.CTkTabview(self.main_frame)
        self.tabview.pack(fill=tk.BOTH, expand=True, pady=10)

        # Ajouter les onglets
        self.tab_progress = self.tabview.add("Progression")
        self.tab_elevation = self.tabview.add("Dénivelés")
        self.tab_speed = self.tabview.add("Vitesses")
        self.tab_sections = self.tabview.add("Sections")

        # Créer les sous-onglets pour chaque catégorie principale
        self.create_progression_subtabs()
        self.create_elevation_subtabs()
        self.create_speed_subtabs()
        self.create_sections_subtabs()

        # Initialiser l'affichage
        self.update_displays()

    def preload_section_data(self, selected_race):
        """Précharger les données des sections pour une course"""
        try:
            # Mettre à jour la liste des sections disponibles
            self.update_section_selector(selected_race)

            section_data = {}

            # Pour chaque section trouvée
            for section_name in self.sections_info.keys():
                print(f"Traitement de la section: {section_name}")  # Debug

                # Simuler la sélection de la section
                if self.section_selector:
                    self.section_selector.set(section_name)

                # Mettre à jour l'affichage des performances pour cette section
                self.update_section_display()

                # Récupérer les données avec filtrage par course
                temps_data = []
                vitesse_data = []
                progression_data = []

                for bib in self.bibs:
                    if str(bib) in self.scraper.all_data:
                        data = self.scraper.all_data[str(bib)]
                        if selected_race == "Toutes les courses" or data['infos']['race_name'] == selected_race:
                            checkpoints = data['checkpoints']

                            # Trouver la section dans les points de passage
                            for i in range(len(checkpoints) - 1):
                                current_section = f"{checkpoints[i]['point']} → {checkpoints[i + 1]['point']}"
                                if current_section == section_name:
                                    try:
                                        # Calculer temps avec la nouvelle méthode
                                        section_time = self.time_diff(checkpoints[i + 1]['race_time'],
                                                                      checkpoints[i]['race_time'])

                                        if section_time is not None:
                                            # Convertir le temps HH:MM:SS en heures pour le calcul de vitesse
                                            h, m, s = map(int, section_time.split(':'))
                                            hours = h + m / 60 + s / 3600

                                            # Calculer vitesse
                                            distance = checkpoints[i + 1]['kilometer'] - checkpoints[i]['kilometer']
                                            speed = distance / hours if hours > 0 else 0

                                        # Calculer vitesse effort
                                        d_plus = checkpoints[i]['elevation_gain'] or 0
                                        d_minus = checkpoints[i]['elevation_loss'] or 0
                                        effort_distance = distance + (d_plus / 1000 * 10) + (d_minus / 1000 * 2)
                                        effort_speed = effort_distance / hours if hours > 0 else 0

                                        # Calculer progression
                                        rank1 = int(checkpoints[i]['rank']) if checkpoints[i]['rank'] else 0
                                        rank2 = int(checkpoints[i + 1]['rank']) if checkpoints[i + 1]['rank'] else 0
                                        progression = rank1 - rank2 if rank1 and rank2 else 0

                                        # Ajouter aux listes de données
                                        temps_data.append([
                                            len(temps_data) + 1,  # Position
                                            bib,  # Dossard
                                            data['infos']['name'],  # Nom
                                            data['infos']['race_name'],  # Course
                                            section_time,  # Temps
                                            f"{speed:.1f} km/h"  # Vitesse
                                        ])

                                        vitesse_data.append([
                                            len(vitesse_data) + 1,
                                            bib,
                                            data['infos']['name'],
                                            data['infos']['race_name'],
                                            f"{speed:.1f} km/h",
                                            f"{effort_speed:.1f} km/h"
                                        ])

                                        progression_data.append([
                                            len(progression_data) + 1,
                                            bib,
                                            data['infos']['name'],
                                            data['infos']['race_name'],
                                            progression,
                                            f"{rank1} → {rank2}"
                                        ])

                                    except Exception as e:
                                        print(
                                            f"Erreur lors du traitement des données du coureur {bib} pour la section {section_name}: {e}")
                                    break

                # Trier les données
                temps_data.sort(key=lambda x: x[4])  # Tri par temps
                vitesse_data.sort(key=lambda x: float(x[4].split()[0]), reverse=True)  # Tri par vitesse
                progression_data.sort(key=lambda x: x[4], reverse=True)  # Tri par progression

                # Mettre à jour les positions après le tri
                for i, row in enumerate(temps_data, 1):
                    row[0] = i
                for i, row in enumerate(vitesse_data, 1):
                    row[0] = i
                for i, row in enumerate(progression_data, 1):
                    row[0] = i

                # Limiter aux 20 meilleurs
                temps_data = temps_data[:20]
                vitesse_data = vitesse_data[:20]
                progression_data = progression_data[:20]

                section_data[section_name] = {
                    'temps': temps_data,
                    'vitesse': vitesse_data,
                    'progression': progression_data,
                    'info': self.sections_info[section_name]
                }

                print(f"Données collectées pour la section {section_name}:")  # Debug
                print(f"Temps: {len(temps_data)} entrées")
                print(f"Vitesse: {len(vitesse_data)} entrées")
                print(f"Progression: {len(progression_data)} entrées")

            return section_data

        except Exception as e:
            print(f"Erreur dans preload_section_data: {str(e)}")
            traceback.print_exc()
            return {}

    def get_unique_races(self):
        races = set()
        races.add("Toutes les courses")
        for bib in self.bibs:
            if str(bib) in self.scraper.all_data:
                race_name = self.scraper.all_data[str(bib)]['infos']['race_name']
                races.add(race_name)
        return sorted(list(races))

    def create_progression_subtabs(self):
        self.progress_tabs = ctk.CTkTabview(self.tab_progress)
        self.progress_tabs.pack(fill=tk.BOTH, expand=True)

        self.progress_global = self.progress_tabs.add("Progression globale")
        self.progress_sections = self.progress_tabs.add("Entre points")

        # Ajouter ScrollArea pour chaque sous-onglet
        self.progress_global_scroll = ctk.CTkScrollableFrame(self.progress_global)
        self.progress_global_scroll.pack(fill=tk.BOTH, expand=True)

        self.progress_sections_scroll = ctk.CTkScrollableFrame(self.progress_sections)
        self.progress_sections_scroll.pack(fill=tk.BOTH, expand=True)

    def create_elevation_subtabs(self):
        self.elevation_tabs = ctk.CTkTabview(self.tab_elevation)
        self.elevation_tabs.pack(fill=tk.BOTH, expand=True)

        self.elevation_climbers = self.elevation_tabs.add("Grimpeurs")
        self.elevation_descenders = self.elevation_tabs.add("Descendeurs")

        self.climbers_scroll = ctk.CTkScrollableFrame(self.elevation_climbers)
        self.climbers_scroll.pack(fill=tk.BOTH, expand=True)

        self.descenders_scroll = ctk.CTkScrollableFrame(self.elevation_descenders)
        self.descenders_scroll.pack(fill=tk.BOTH, expand=True)

    def create_analyses_index_html(self, courses):
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Analyses TOP</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                .category-section {
                    margin-bottom: 2rem;
                    padding: 1rem;
                    background-color: #f8f9fa;
                    border-radius: 8px;
                }
            </style>
        </head>
        <body>
            <div class="container py-5">
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <h1>Analyses TOP</h1>
                    <select id="courseSelect" class="form-select" style="width: auto;">
        """

        # Ajouter les options de course
        for course in courses:
            html += f'<option value="{course}">{course}</option>'

        html += """
                    </select>
                </div>
                <div class="mb-4">
                    <a href="../index.html" class="btn btn-secondary">← Retour au tableau des coureurs</a>
                </div>

                <div class="row">
                    <div class="col-md-4">
                        <div class="category-section">
                            <h3>Progression</h3>
                            <ul class="analysis-links"></ul>
                        </div>
                    </div>

                    <div class="col-md-4">
                        <div class="category-section">
                            <h3>Dénivelés</h3>
                            <ul class="analysis-links"></ul>
                        </div>
                    </div>

                    <div class="col-md-4">
                        <div class="category-section">
                            <h3>Vitesses</h3>
                            <ul class="analysis-links"></ul>
                        </div>
                    </div>
                </div>

                <div class="row mt-4">
                    <div class="col-12">
                        <div class="category-section">
                            <h3>Sections</h3>
                            <ul class="analysis-links">
                                <li><a href="analyse_sections.html">Analyse par sections</a></li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>

            <script>
            document.getElementById('courseSelect').addEventListener('change', function() {
                const course = this.value;
                const suffix = course === 'Toutes les courses' ? '' : '_' + course.toLowerCase().replace(/ /g, '_');
                updateLinks(suffix);
            });

            function updateLinks(suffix) {
                const links = {
                    'Progression': {
                        'Progression globale': `progression_globale${suffix}.html`,
                        'Progression entre points': `progression_sections${suffix}.html`
                    },
                    'Dénivelés': {
                        'Top Grimpeurs': `grimpeurs${suffix}.html`,
                        'Top Descendeurs': `descendeurs${suffix}.html`
                    },
                    'Vitesses': {
                        'Vitesse moyenne': `vitesse_moyenne${suffix}.html`,
                        'Vitesse effort': `vitesse_effort${suffix}.html`,
                        'Vitesse par section': `vitesse_sections${suffix}.html`
                    }
                };

                document.querySelectorAll('.category-section').forEach(section => {
                    const title = section.querySelector('h3').textContent;
                    if (title in links) {  // Ne mettre à jour que les sections avec des liens dynamiques
                        const ul = section.querySelector('ul');
                        ul.innerHTML = '';

                        Object.entries(links[title]).forEach(([name, url]) => {
                            ul.innerHTML += `<li><a href="${url}">${name}</a></li>`;
                        });
                    }
                });
            }

            // Initialize links
            updateLinks('');
            </script>
        </body>
        </html>
        """
        return html

    def create_speed_subtabs(self):
        self.speed_tabs = ctk.CTkTabview(self.tab_speed)
        self.speed_tabs.pack(fill=tk.BOTH, expand=True)

        self.speed_avg = self.speed_tabs.add("Vitesse moyenne")
        self.speed_effort = self.speed_tabs.add("Vitesse effort")
        self.speed_sections = self.speed_tabs.add("Entre points")

        self.speed_avg_scroll = ctk.CTkScrollableFrame(self.speed_avg)
        self.speed_avg_scroll.pack(fill=tk.BOTH, expand=True)

        self.speed_effort_scroll = ctk.CTkScrollableFrame(self.speed_effort)
        self.speed_effort_scroll.pack(fill=tk.BOTH, expand=True)

        self.speed_sections_scroll = ctk.CTkScrollableFrame(self.speed_sections)
        self.speed_sections_scroll.pack(fill=tk.BOTH, expand=True)

    def create_sections_subtabs(self):
        self.sections_frame = ctk.CTkFrame(self.tab_sections)
        self.sections_frame.pack(fill=tk.BOTH, expand=True)

        # Ajouter le sélecteur de sections
        self.section_frame.pack(side=tk.LEFT, padx=20)
        ctk.CTkLabel(self.section_frame, text="Section:").pack(side=tk.LEFT, padx=5)
        self.section_selector = ctk.CTkComboBox(
            self.section_frame,
            values=[],
            command=self.on_section_selected
        )
        self.section_selector.pack(side=tk.LEFT, padx=5)

        # Frame pour les résultats de section avec scroll
        self.section_results_scroll = ctk.CTkScrollableFrame(self.sections_frame)
        self.section_results_scroll.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def on_race_selected(self, selection):
        # Mettre à jour les sections disponibles
        self.update_section_selector(selection)
        # Mettre à jour tous les affichages
        self.update_displays()

    def on_section_selected(self, selection):
        # Mettre à jour l'affichage des performances de la section
        self.update_section_display()

    def update_section_selector(self, race):
        """Mettre à jour la liste des sections avec les données associées"""
        self.sections_info = {}  # Réinitialiser les infos de section
        for bib in self.bibs:
            if str(bib) in self.scraper.all_data:
                data = self.scraper.all_data[str(bib)]
                if race == "Toutes les courses" or data['infos']['race_name'] == race:
                    checkpoints = data['checkpoints']
                    for i in range(len(checkpoints) - 1):
                        section_name = f"{checkpoints[i]['point']} → {checkpoints[i + 1]['point']}"
                        if section_name not in self.sections_info:
                            self.sections_info[section_name] = {
                                'name': section_name,
                                'distance': checkpoints[i + 1]['kilometer'] - checkpoints[i]['kilometer'],
                                'elevation_gain': checkpoints[i + 1]['elevation_gain'],
                                'elevation_loss': checkpoints[i + 1]['elevation_loss']
                            }

        # Mettre à jour le ComboBox avec les noms des sections
        section_names = sorted(list(self.sections_info.keys()))
        self.section_selector.configure(values=section_names)
        if section_names:
            self.section_selector.set(section_names[0])

    def update_displays(self):
        """Mettre à jour tous les affichages en fonction de la course sélectionnée"""
        self.clear_all_displays()
        selected_race = self.race_selector.get()

        # Mettre à jour les progressions
        self.update_progression_displays(selected_race)

        # Mettre à jour les dénivelés
        self.update_elevation_displays(selected_race)

        # Mettre à jour les vitesses
        self.update_speed_displays(selected_race)

        # Mettre à jour l'affichage des sections
        self.update_section_display()

    def clear_all_displays(self):
        """Effacer tous les affichages existants"""
        for widget in self.progress_global_scroll.winfo_children():
            widget.destroy()
        for widget in self.progress_sections_scroll.winfo_children():
            widget.destroy()
        for widget in self.climbers_scroll.winfo_children():
            widget.destroy()
        for widget in self.descenders_scroll.winfo_children():
            widget.destroy()
        for widget in self.speed_avg_scroll.winfo_children():
            widget.destroy()
        for widget in self.speed_effort_scroll.winfo_children():
            widget.destroy()
        for widget in self.speed_sections_scroll.winfo_children():
            widget.destroy()
        for widget in self.section_results_scroll.winfo_children():
            widget.destroy()

    def create_table(self, parent, columns, headers, data, height=10, tooltips=None):
        """Créer un tableau personnalisé avec style uniforme et infobulles"""
        style = ttk.Style()
        style.configure(
            "Custom.Treeview",
            background="#2b2b2b",
            foreground="white",
            fieldbackground="#2b2b2b",
            rowheight=30
        )
        style.configure(
            "Custom.Treeview.Heading",
            background="#2b2b2b",
            foreground="white"
        )

        tree = ttk.Treeview(
            parent,
            columns=columns,
            show="headings",
            height=height,
            style="Custom.Treeview"
        )

        # Création des infobulles
        tooltip = None
        if tooltips:
            from tkinter import messagebox
            def show_tooltip(event):
                column = tree.identify_column(event.x)
                col_id = int(column.replace('#', '')) - 1
                if col_id < len(columns) and columns[col_id] in tooltips:
                    messagebox.showinfo("Information", tooltips[columns[col_id]])

            tree.bind('<Button-3>', show_tooltip)  # Clic droit pour afficher l'infobulle

        for col in columns:
            header_text = headers[col]
            if tooltips and col in tooltips:
                header_text += " (❓)"  # Ajouter un indicateur visuel
            tree.heading(col, text=header_text)
            tree.column(col, width=headers.get(f"{col}_width", 100), anchor="center")

        # Ajouter les données
        for row in data:
            tree.insert("", "end", values=row)

        return tree

    def create_section_info_card(self, parent, section_info):
        """Créer une carte d'information pour une section avec infobulles"""
        frame = ctk.CTkFrame(parent)
        frame.pack(fill=tk.X, padx=5, pady=5)

        title = ctk.CTkLabel(
            frame,
            text=section_info['name'],
            font=("Arial", 16, "bold")
        )
        title.pack(pady=5)

        # Création d'un frame pour les informations avec infobulles
        info_frame = ctk.CTkFrame(frame)
        info_frame.pack(pady=5)

        # Distance
        distance_frame = ctk.CTkFrame(info_frame)
        distance_frame.pack(side=tk.LEFT, padx=10)
        distance_label = ctk.CTkLabel(
            distance_frame,
            text=f"Distance: {section_info['distance']:.1f}km"
        )
        distance_label.pack(side=tk.LEFT)

        def show_distance_info():
            messagebox.showinfo("Information",
                                "Distance horizontale entre les deux points de la section.")

        distance_info = ctk.CTkButton(
            distance_frame,
            text="❓",
            width=20,
            command=show_distance_info
        )
        distance_info.pack(side=tk.LEFT, padx=2)

        # Dénivelé positif
        dplus_frame = ctk.CTkFrame(info_frame)
        dplus_frame.pack(side=tk.LEFT, padx=10)
        dplus_label = ctk.CTkLabel(
            dplus_frame,
            text=f"D+: {section_info['elevation_gain']}m"
        )
        dplus_label.pack(side=tk.LEFT)

        def show_dplus_info():
            messagebox.showinfo("Information",
                                "Dénivelé positif accumulé sur la section.\n"
                                "Représente la somme des montées uniquement.")

        dplus_info = ctk.CTkButton(
            dplus_frame,
            text="❓",
            width=20,
            command=show_dplus_info
        )
        dplus_info.pack(side=tk.LEFT, padx=2)

        # Dénivelé négatif
        dminus_frame = ctk.CTkFrame(info_frame)
        dminus_frame.pack(side=tk.LEFT, padx=10)
        dminus_label = ctk.CTkLabel(
            dminus_frame,
            text=f"D-: {section_info['elevation_loss']}m"
        )
        dminus_label.pack(side=tk.LEFT)

        def show_dminus_info():
            messagebox.showinfo("Information",
                                "Dénivelé négatif accumulé sur la section.\n"
                                "Représente la somme des descentes uniquement.")

        dminus_info = ctk.CTkButton(
            dminus_frame,
            text="❓",
            width=20,
            command=show_dminus_info
        )
        dminus_info.pack(side=tk.LEFT, padx=2)

        return frame


    def update_progression_displays(self, selected_race):
        """Mettre à jour les affichages de progression"""
        # Progression globale
        global_progressions = []
        for bib in self.bibs:
            if str(bib) in self.scraper.all_data:
                data = self.scraper.all_data[str(bib)]
                if selected_race == "Toutes les courses" or data['infos']['race_name'] == selected_race:
                    checkpoints = data['checkpoints']
                    if len(checkpoints) >= 2:
                        first_rank = None
                        last_rank = None

                        for cp in checkpoints:
                            if cp['rank'] is not None:
                                try:
                                    rank = int(cp['rank'])
                                    if first_rank is None:
                                        first_rank = rank
                                    last_rank = rank
                                except ValueError:
                                    continue

                        if first_rank is not None and last_rank is not None:
                            progression = first_rank - last_rank
                            global_progressions.append({
                                'progression': progression,
                                'bib': bib,
                                'name': data['infos']['name'],
                                'race': data['infos']['race_name'],
                                'start_pos': first_rank,
                                'end_pos': last_rank
                            })

        # Trier et afficher les meilleures progressions
        global_progressions.sort(key=lambda x: x['progression'], reverse=True)

        columns = ["rank", "bib", "name", "race", "start_pos", "end_pos", "progression"]
        headers = {
            "rank": "Position",
            "rank_width": 80,
            "bib": "Dossard",
            "bib_width": 80,
            "name": "Nom",
            "name_width": 200,
            "race": "Course",
            "race_width": 150,
            "start_pos": "Pos. départ",
            "start_pos_width": 100,
            "end_pos": "Pos. finale",
            "end_pos_width": 100,
            "progression": "Progression",
            "progression_width": 100
        }

        data = [
            (
                i + 1,
                prog['bib'],
                prog['name'],
                prog['race'],
                prog['start_pos'],
                prog['end_pos'],
                f"+{prog['progression']}" if prog['progression'] > 0 else str(prog['progression'])
            )
            for i, prog in enumerate(global_progressions[:20])
        ]

        # Ajouter les tooltips pour la progression globale
        tooltips = {
            "progression": "Places gagnées entre le premier et le dernier point de passage.",
            "start_pos": "Position au premier point de chronométrage.",
            "end_pos": "Position finale du coureur."
        }

        if data:
            ctk.CTkLabel(
                self.progress_global_scroll,
                text="Top 20 des meilleures progressions (Clic droit sur les en-têtes pour plus d'informations)",
                font=("Arial", 16, "bold")
            ).pack(pady=10)

            tree = self.create_table(self.progress_global_scroll, columns, headers, data, tooltips=tooltips)
            tree.pack(fill=tk.X, padx=5, pady=5)

        # Ajouter les tooltips pour la progression entre points
        section_tooltips = {
            "section": "Points de passage entre lesquels la progression est calculée",
            "progression": "Nombre de places gagnées sur cette section spécifique",
            "ranks": "Positions au début et à la fin de la section"
        }


        # Progression entre points
        section_progressions = []
        for bib in self.bibs:
            if str(bib) in self.scraper.all_data:
                data = self.scraper.all_data[str(bib)]
                if selected_race == "Toutes les courses" or data['infos']['race_name'] == selected_race:
                    checkpoints = data['checkpoints']

                    for i in range(len(checkpoints) - 1):
                        if checkpoints[i]['rank'] and checkpoints[i + 1]['rank']:
                            try:
                                rank1 = int(checkpoints[i]['rank'])
                                rank2 = int(checkpoints[i + 1]['rank'])
                                progression = rank1 - rank2
                                if progression > 0:
                                    section_progressions.append({
                                        'progression': progression,
                                        'bib': bib,
                                        'name': data['infos']['name'],
                                        'race': data['infos']['race_name'],
                                        'from_point': checkpoints[i]['point'],
                                        'to_point': checkpoints[i + 1]['point'],
                                        'start_rank': rank1,
                                        'end_rank': rank2
                                    })
                            except ValueError:
                                continue

        section_progressions.sort(key=lambda x: x['progression'], reverse=True)

        if section_progressions:
            ctk.CTkLabel(
                self.progress_sections_scroll,
                text="Top 20 des meilleures progressions entre points",
                font=("Arial", 16, "bold")
            ).pack(pady=10)

            columns = ["rank", "bib", "name", "race", "section", "progression", "ranks"]
            headers = {
                "rank": "Position",
                "rank_width": 80,
                "bib": "Dossard",
                "bib_width": 80,
                "name": "Nom",
                "name_width": 200,
                "race": "Course",
                "race_width": 150,
                "section": "Section",
                "section_width": 300,
                "progression": "Progression",
                "progression_width": 100,
                "ranks": "Classements",
                "ranks_width": 150
            }

            data = [
                (
                    i + 1,
                    prog['bib'],
                    prog['name'],
                    prog['race'],
                    f"{prog['from_point']} → {prog['to_point']}",
                    f"+{prog['progression']}",
                    f"{prog['start_rank']} → {prog['end_rank']}"
                )
                for i, prog in enumerate(section_progressions[:20])
            ]

            tree = self.create_table(self.progress_sections_scroll, columns, headers, data)
            tree.pack(fill=tk.X, padx=5, pady=5)

    def update_elevation_displays(self, selected_race):
        """Mettre à jour les affichages de dénivelé avec les calculs corrigés"""
        # Calcul pour les grimpeurs
        climbers = []
        for bib in self.bibs:
            if str(bib) in self.scraper.all_data:
                data = self.scraper.all_data[str(bib)]
                if selected_race == "Toutes les courses" or data['infos']['race_name'] == selected_race:
                    checkpoints = data['checkpoints']

                    for i in range(len(checkpoints) - 1):
                        if checkpoints[i + 1]['elevation_gain'] > 100:  # sections significatives
                            try:
                                elevation_gain = checkpoints[i + 1]['elevation_gain']
                                section_time = self.time_diff(checkpoints[i + 1]['race_time'],
                                                              checkpoints[i]['race_time'])

                                if section_time:
                                    # Convertir le temps en heures
                                    h, m, s = map(int, section_time.split(':'))
                                    time_hours = h + m / 60 + s / 3600

                                    distance = checkpoints[i + 1]['kilometer'] - checkpoints[i]['kilometer']

                                    if time_hours > 0:
                                        # Vitesse verticale en m/h
                                        vertical_speed = elevation_gain / time_hours

                                        # Pente moyenne en %
                                        slope_percentage = (elevation_gain / (
                                                    distance * 1000)) * 100 if distance > 0 else 0

                                        section_name = f"{checkpoints[i]['point']} → {checkpoints[i + 1]['point']}"

                                        climbers.append({
                                            'speed': vertical_speed,
                                            'bib': bib,
                                            'name': data['infos']['name'],
                                            'race': data['infos']['race_name'],
                                            'elevation_gain': elevation_gain,
                                            'time_hours': time_hours,
                                            'time': section_time,
                                            'slope': slope_percentage,
                                            'section': section_name
                                        })
                            except Exception as e:
                                print(f"Erreur sur segment montée {i} pour dossard {bib}: {e}")
                                continue

        climbers.sort(key=lambda x: x['speed'], reverse=True)

        # Affichage des grimpeurs
        if climbers:
            ctk.CTkLabel(
                self.climbers_scroll,
                text="Top 20 des meilleurs grimpeurs (Clic droit sur les en-têtes pour plus d'informations)",
                font=("Arial", 16, "bold")
            ).pack(pady=10)

            columns = ["rank", "bib", "name", "race", "section", "elevation", "time", "speed", "slope"]
            headers = {
                "rank": "Position",
                "rank_width": 80,
                "bib": "Dossard",
                "bib_width": 80,
                "name": "Nom",
                "name_width": 200,
                "race": "Course",
                "race_width": 150,
                "section": "Section",
                "section_width": 200,
                "elevation": "D+",
                "elevation_width": 100,
                "time": "Temps",
                "time_width": 100,
                "speed": "Vitesse",
                "speed_width": 100,
                "slope": "Pente",
                "slope_width": 100
            }

            data = [
                (
                    i + 1,
                    climb['bib'],
                    climb['name'],
                    climb['race'],
                    climb['section'],
                    f"{climb['elevation_gain']}m",
                    climb['time'],
                    f"{climb['speed']:.1f} m/h",
                    f"{climb['slope']:.1f}%"
                )
                for i, climb in enumerate(climbers[:20])
            ]

            tree = self.create_table(self.climbers_scroll, columns, headers, data)
            tree.pack(fill=tk.X, padx=5, pady=5)

        # Calcul pour les descendeurs
        descenders = []
        for bib in self.bibs:
            if str(bib) in self.scraper.all_data:
                data = self.scraper.all_data[str(bib)]
                if selected_race == "Toutes les courses" or data['infos']['race_name'] == selected_race:
                    checkpoints = data['checkpoints']

                    for i in range(len(checkpoints) - 1):
                        if checkpoints[i + 1]['elevation_loss'] > 100:  # sections significatives
                            try:
                                elevation_loss = checkpoints[i + 1]['elevation_loss']
                                section_time = self.time_diff(checkpoints[i + 1]['race_time'],
                                                              checkpoints[i]['race_time'])

                                if section_time:
                                    # Convertir le temps en heures
                                    h, m, s = map(int, section_time.split(':'))
                                    time_hours = h + m / 60 + s / 3600

                                    distance = checkpoints[i + 1]['kilometer'] - checkpoints[i]['kilometer']

                                    if time_hours > 0:
                                        # Vitesse verticale en m/h
                                        vertical_speed = elevation_loss / time_hours

                                        # Pente moyenne en %
                                        slope_percentage = (elevation_loss / (
                                                    distance * 1000)) * 100 if distance > 0 else 0

                                        section_name = f"{checkpoints[i]['point']} → {checkpoints[i + 1]['point']}"

                                        descenders.append({
                                            'speed': vertical_speed,
                                            'bib': bib,
                                            'name': data['infos']['name'],
                                            'race': data['infos']['race_name'],
                                            'elevation_loss': elevation_loss,
                                            'time_hours': time_hours,
                                            'time': section_time,
                                            'slope': slope_percentage,
                                            'section': section_name
                                        })
                            except Exception as e:
                                print(f"Erreur sur segment descente {i} pour dossard {bib}: {e}")
                                continue

        descenders.sort(key=lambda x: x['speed'], reverse=True)

        # Affichage des descendeurs
        if descenders:
            ctk.CTkLabel(
                self.descenders_scroll,
                text="Top 20 des meilleurs descendeurs (Clic droit sur les en-têtes pour plus d'informations)",
                font=("Arial", 16, "bold")
            ).pack(pady=10)

            data = [
                (
                    i + 1,
                    desc['bib'],
                    desc['name'],
                    desc['race'],
                    desc['section'],
                    f"{desc['elevation_loss']}m",
                    desc['time'],
                    f"{desc['speed']:.1f} m/h",
                    f"{desc['slope']:.1f}%"
                )
                for i, desc in enumerate(descenders[:20])
            ]

            tree = self.create_table(self.descenders_scroll, columns, headers, data)
            tree.pack(fill=tk.X, padx=5, pady=5)
            
    def update_speed_displays(self, selected_race):
        """Mettre à jour les affichages de vitesse"""
        speeds = []
        efforts = []
        section_speeds = []

        for bib in self.bibs:
            if str(bib) in self.scraper.all_data:
                data = self.scraper.all_data[str(bib)]
                if selected_race == "Toutes les courses" or data['infos']['race_name'] == selected_race:
                    checkpoints = data['checkpoints']

                    # Calcul des vitesses moyennes
                    avg_speed = 0
                    avg_effort = 0
                    count = 0

                    for cp in checkpoints:
                        try:
                            speed = float(cp['speed'].replace('km/h', '').strip())
                            effort = float(cp['effort_speed'].replace('km/h', '').strip())
                            avg_speed += speed
                            avg_effort += effort
                            count += 1
                        except:
                            continue

                    if count > 0:
                        speeds.append({
                            'speed': avg_speed / count,
                            'bib': bib,
                            'name': data['infos']['name'],
                            'race': data['infos']['race_name']
                        })

                        efforts.append({
                            'effort': avg_effort / count,
                            'bib': bib,
                            'name': data['infos']['name'],
                            'race': data['infos']['race_name']
                        })

                    # Calcul des vitesses par section
                    for i in range(len(checkpoints) - 1):
                        try:
                            # Utiliser time_diff pour obtenir le temps au format HH:MM:SS
                            time_diff_str = self.time_diff(checkpoints[i + 1]['race_time'],
                                                           checkpoints[i]['race_time'])

                            if time_diff_str:
                                # Convertir le temps HH:MM:SS en heures
                                hours, minutes, seconds = map(int, time_diff_str.split(':'))
                                segment_time = hours + minutes / 60 + seconds / 3600
                                distance = checkpoints[i + 1]['kilometer'] - checkpoints[i]['kilometer']

                                if segment_time > 0:
                                    section_speed = distance / segment_time
                                    section_speeds.append({
                                        'speed': section_speed,
                                        'bib': bib,
                                        'name': data['infos']['name'],
                                        'race': data['infos']['race_name'],
                                        'from_point': checkpoints[i]['point'],
                                        'to_point': checkpoints[i + 1]['point'],
                                        'distance': distance
                                    })
                        except Exception as e:
                            print(f"Erreur calcul vitesse section {i} pour dossard {bib}: {e}")
                            continue

        # Afficher les vitesses moyennes
        speeds.sort(key=lambda x: x['speed'], reverse=True)
        self.display_speed_table(
            self.speed_avg_scroll,
            speeds[:20],
            "Top 20 des meilleures vitesses moyennes",
            "speed"
        )

        # Afficher les vitesses effort
        efforts.sort(key=lambda x: x['effort'], reverse=True)
        self.display_speed_table(
            self.speed_effort_scroll,
            efforts[:20],
            "Top 20 des meilleures vitesses effort",
            "effort"
        )

        # Afficher les vitesses par section
        section_speeds.sort(key=lambda x: x['speed'], reverse=True)
        self.display_section_speed_table(
            self.speed_sections_scroll,
            section_speeds[:20]
        )

    def display_speed_table(self, parent, data, title, speed_type):
        """Afficher un tableau de vitesses avec infobulles"""
        if not data:
            return

        tooltips = {
            "speed": {
                'speed': "Moyenne des vitesses instantanées sur l'ensemble du parcours (sans tenir compte du dénivelé).",
                'effort': "Moyenne des vitesses effort qui prennent en compte le dénivelé. Permet de comparer l'intensité réelle de l'effort."
            }[speed_type]
        }

        ctk.CTkLabel(
            parent,
            text=title + " (Clic droit sur les en-têtes pour plus d'informations)",
            font=("Arial", 16, "bold")
        ).pack(pady=10)

        columns = ["rank", "bib", "name", "race", "speed"]
        headers = {
            "rank": "Position",
            "rank_width": 80,
            "bib": "Dossard",
            "bib_width": 80,
            "name": "Nom",
            "name_width": 200,
            "race": "Course",
            "race_width": 150,
            "speed": {
                'speed': "Vitesse moyenne",
                'effort': "Vitesse effort moyenne"
            }[speed_type],
            "speed_width": 100
        }

        table_data = [
            (
                i + 1,
                item['bib'],
                item['name'],
                item['race'],
                f"{item[speed_type]:.1f} km/h"
            )
            for i, item in enumerate(data)
        ]

        tree = self.create_table(parent, columns, headers, table_data, tooltips=tooltips)
        tree.pack(fill=tk.X, padx=5, pady=5)

    def display_section_speed_table(self, parent, data):
        """Afficher un tableau de vitesses par section avec infobulles"""
        if not data:
            return

        tooltips = {
            "speed": "Vitesse moyenne réelle sur la section calculée avec (Distance / Temps).\nNe prend pas en compte le dénivelé.",
            "distance": "Distance horizontale entre les deux points de la section.",
            "section": "Points de début et de fin de la section."
        }

        ctk.CTkLabel(
            parent,
            text="Top 20 des meilleures vitesses par section (Clic droit sur les en-têtes pour plus d'informations)",
            font=("Arial", 16, "bold")
        ).pack(pady=10)

        columns = ["rank", "bib", "name", "race", "section", "distance", "speed"]
        headers = {
            "rank": "Position",
            "rank_width": 80,
            "bib": "Dossard",
            "bib_width": 80,
            "name": "Nom",
            "name_width": 200,
            "race": "Course",
            "race_width": 150,
            "section": "Section",
            "section_width": 300,
            "distance": "Distance",
            "distance_width": 100,
            "speed": "Vitesse",
            "speed_width": 100
        }

        table_data = [
            (
                i + 1,
                item['bib'],
                item['name'],
                item['race'],
                f"{item['from_point']} → {item['to_point']}",
                f"{item['distance']:.1f} km",
                f"{item['speed']:.1f} km/h"
            )
            for i, item in enumerate(data)
        ]

        tree = self.create_table(parent, columns, headers, table_data, tooltips=tooltips)
        tree.pack(fill=tk.X, padx=5, pady=5)

    def convert_time_to_seconds(self, time_str):
        """Convertit un temps au format HH:MM:SS en secondes"""
        try:
            hours, minutes, seconds = map(int, time_str.split(':'))
            return hours * 3600 + minutes * 60 + seconds
        except Exception as e:
            print(f"Erreur lors de la conversion du temps {time_str}: {e}")
            return None

    def update_section_display(self):
        """Mettre à jour l'affichage des performances par section"""
        # Nettoyer l'affichage existant
        for widget in self.section_results_scroll.winfo_children():
            widget.destroy()

        selected_race = self.race_selector.get()
        selected_section = self.section_selector.get()

        if not selected_section or selected_section not in self.sections_info:
            return

        # Utiliser les informations de section stockées
        section_info = self.sections_info[selected_section]

        # Collecter les performances pour la section sélectionnée
        section_performances = []

        for bib in self.bibs:
            if str(bib) in self.scraper.all_data:
                data = self.scraper.all_data[str(bib)]
                if selected_race == "Toutes les courses" or data['infos']['race_name'] == selected_race:
                    checkpoints = data['checkpoints']

                    for i in range(len(checkpoints) - 1):
                        section = f"{checkpoints[i]['point']} → {checkpoints[i + 1]['point']}"
                        if section == selected_section:
                            try:
                                # Calculer le temps de la section en gardant le format HH:MM:SS
                                section_time = self.time_diff(
                                    checkpoints[i + 1]['race_time'],
                                    checkpoints[i]['race_time']
                                )

                                if not section_time:
                                    continue

                                # Pour le calcul des vitesses, on a besoin du temps en heures
                                h, m, s = map(int, section_time.split(':'))
                                hours = h + m / 60 + s / 3600

                                # Calculer la vitesse si le temps est valide
                                if hours > 0:
                                    speed = section_info['distance'] / hours

                                    # Calculer la vitesse effort
                                    effort_speed = (
                                                           section_info['distance'] +
                                                           (section_info['elevation_gain'] / 1000 * 10) +
                                                           (section_info['elevation_loss'] / 1000 * 2)
                                                   ) / hours

                                    # Calculer la progression de classement
                                    rank1 = int(checkpoints[i]['rank']) if checkpoints[i]['rank'] else 0
                                    rank2 = int(checkpoints[i + 1]['rank']) if checkpoints[i + 1]['rank'] else 0
                                    progression = rank1 - rank2 if rank1 and rank2 else 0

                                    # Calculer la tendance (montée/descente/plat)
                                    total_distance_m = section_info['distance'] * 1000
                                    if total_distance_m > 0:
                                        elevation_ratio = (
                                                (section_info['elevation_gain'] - section_info['elevation_loss'])
                                                / total_distance_m
                                        )
                                        if elevation_ratio > 0.05:
                                            tendency = "↗️"
                                        elif elevation_ratio < -0.05:
                                            tendency = "↘️"
                                        else:
                                            tendency = "➡️"
                                    else:
                                        tendency = "➡️"

                                    # Ajouter les performances calculées
                                    section_performances.append({
                                        'bib': bib,
                                        'name': data['infos']['name'],
                                        'race': data['infos']['race_name'],
                                        'time': section_time,  # Format HH:MM:SS
                                        'speed': speed,
                                        'effort_speed': effort_speed,
                                        'progression': progression,
                                        'start_rank': rank1,
                                        'end_rank': rank2,
                                        'tendency': tendency
                                    })

                            except Exception as e:
                                print(f"Erreur lors du calcul des performances: {e}")
                                continue

            # Tri des performances

        def time_to_seconds(time_str):
            """Convertit HH:MM:SS en secondes pour le tri"""
            h, m, s = map(int, time_str.split(':'))
            return h * 3600 + m * 60 + s

            # Pour le tri par temps

        section_performances.sort(key=lambda x: time_to_seconds(x['time']))

        if section_info:
            # Créer la carte d'information de la section
            self.create_section_info_card(self.section_results_scroll, section_info)

            # Créer les tableaux de performance si on a des données
            if section_performances:
                # 1. Classement par temps
                section_performances.sort(key=lambda x: x['time'])
                self.create_section_performance_table(
                    self.section_results_scroll,
                    section_performances[:20],
                    "Top 20 temps sur la section",
                    'time'
                )

                # 2. Classement par vitesse
                section_performances.sort(key=lambda x: x['speed'], reverse=True)
                self.create_section_performance_table(
                    self.section_results_scroll,
                    section_performances[:20],
                    "Top 20 vitesses sur la section",
                    'speed'
                )

                # 3. Classement par vitesse effort
                section_performances.sort(key=lambda x: x['effort_speed'], reverse=True)
                self.create_section_performance_table(
                    self.section_results_scroll,
                    section_performances[:20],
                    "Top 20 vitesses effort sur la section",
                    'effort'
                )

                # 4. Classement par progression
                section_performances.sort(key=lambda x: x['progression'], reverse=True)
                self.create_section_performance_table(
                    self.section_results_scroll,
                    section_performances[:20],
                    "Top 20 progressions sur la section",
                    'progression'
                )

    def calculate_effort_speed(self, distance, time_seconds, elevation_gain, elevation_loss):
        """
        Calcule la vitesse effort en prenant en compte le dénivelé

        La formule utilisée est :
        Vitesse effort = (distance + (D+ * facteur_montée) + (D- * facteur_descente)) / temps

        Où:
        - facteur_montée = 10 (100m de D+ équivaut à 1km de distance)
        - facteur_descente = 2 (100m de D- équivaut à 0.2km de distance)
        """
        if time_seconds == 0:
            return 0

        # Conversion des dénivelés en kilomètres équivalents
        elevation_gain_factor = 10  # 1000m D+ = 10km de distance
        elevation_loss_factor = 2  # 1000m D- = 2km de distance

        equivalent_distance = (
                distance +  # Distance réelle
                (elevation_gain / 1000 * elevation_gain_factor) +  # Distance équivalente montée
                (elevation_loss / 1000 * elevation_loss_factor)  # Distance équivalente descente
        )

        hours = time_seconds / 3600
        effort_speed = equivalent_distance / hours

        return effort_speed

    def create_section_performance_table(self, parent, data, title, performance_type):
        """Créer un tableau de performances pour une section spécifique avec tendance"""
        if not data:
            return

        frame = ctk.CTkFrame(parent)
        frame.pack(fill=tk.X, padx=5, pady=10)

        tooltips = {
            "performance": {
                'time': (
                    "Temps réel mis pour parcourir la section.\n"
                    "Calculé comme la différence entre les temps de passage aux deux points.\n"
                    "Inclut les temps d'arrêt éventuels."
                ),
                'speed': (
                    "Vitesse moyenne réelle sur la section.\n"
                    "Calculée avec : Distance / Temps total\n"
                    "Ne prend pas en compte le dénivelé."
                ),
                'effort': (
                    "Vitesse effort qui normalise la performance selon le terrain.\n"
                    "Calculée en prenant en compte :\n"
                    "- La distance réelle\n"
                    "- Le dénivelé positif (facteur 10)\n"
                    "- Le dénivelé négatif (facteur 2)\n"
                    "Permet de comparer les performances sur des terrains différents."
                ),
                'progression': (
                    "Évolution du classement sur la section.\n"
                    "Nombre de places gagnées (valeur positive)\n"
                    "ou perdues (valeur négative)."
                )
            }[performance_type],
            "tendency": "Indication du profil de la section:\n↗️ Montée (>5%)\n➡️ Plat\n↘️ Descente (>5%)"
        }

        ctk.CTkLabel(
            frame,
            text=title + " (Clic droit sur les en-têtes pour plus d'informations)",
            font=("Arial", 14, "bold")
        ).pack(pady=5)

        columns = ["rank", "bib", "name", "race", "performance", "tendency"]
        headers = {
            "rank": "Position",
            "rank_width": 80,
            "bib": "Dossard",
            "bib_width": 80,
            "name": "Nom",
            "name_width": 200,
            "race": "Course",
            "race_width": 150,
            "performance": {
                'time': "Temps",
                'speed': "Vitesse",
                'effort': "Vitesse effort",
                'progression': "Progression"
            }[performance_type],
            "performance_width": 150,
            "tendency": "Tendance",
            "tendency_width": 80
        }

        def format_performance(item):
            if performance_type == 'time':
                return item['time']  # Déjà au format HH:MM:SS
            elif performance_type == 'speed':
                return f"{item['speed']:.1f} km/h"
            elif performance_type == 'effort':
                return f"{item['effort_speed']:.1f} km/h"
            elif performance_type == 'progression':
                return f"+{item['progression']}" if item['progression'] > 0 else str(item['progression'])

        table_data = [
            (
                i + 1,
                item['bib'],
                item['name'],
                item['race'],
                format_performance(item),
                item.get('tendency', '➡️')
            )
            for i, item in enumerate(data)
        ]

        tree = self.create_table(frame, columns, headers, table_data, tooltips=tooltips)
        tree.pack(fill=tk.X, padx=5, pady=5)

    def time_diff(self, time2, time1):
        """
        Calcule la différence entre deux temps au format HH:MM:SS, gère >24h
        Retourne le résultat au format HH:MM:SS
        """
        try:
            # Séparer les composantes des temps
            h1, m1, s1 = map(int, time1.split(':'))
            h2, m2, s2 = map(int, time2.split(':'))

            # Calculer chaque composante séparément
            total_h = h2 - h1
            total_m = m2 - m1
            total_s = s2 - s1

            # Gérer les retenues
            if total_s < 0:
                total_s += 60
                total_m -= 1

            if total_m < 0:
                total_m += 60
                total_h -= 1

            # total_h peut être positif ou négatif ici, c'est normal pour >24h

            return f"{total_h:02d}:{total_m:02d}:{total_s:02d}"

        except Exception as e:
            print(f"Erreur lors du calcul de différence de temps: {e}")
            return None

    def export_analyses(self):
        try:
            # Timestamp pour le nom du dossier
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            analysis_dir = f"analyses_{timestamp}"
            os.makedirs(analysis_dir, exist_ok=True)

            # Récupérer la liste complète des courses
            all_courses = set(["Toutes les courses"])
            for bib in self.scraper.all_data:
                race_name = self.scraper.all_data[bib]['infos']['race_name']
                all_courses.add(race_name)

            courses = sorted(list(all_courses))

            # Pour chaque course, générer tous les fichiers d'analyse
            for course in courses:
                normalized_course = course.lower().replace(' ', '_')
                if course != "Toutes les courses":
                    normalized_course = normalized_course.encode('ascii', 'ignore').decode()

                # Liste des types d'analyses à générer
                analysis_types = {
                    'progression_globale': (self.get_progression_global_data,
                                            ["Position", "Dossard", "Nom", "Course", "Pos. départ", "Pos. finale",
                                             "Progression"]),
                    'progression_sections': (self.get_progression_sections_data,
                                             ["Position", "Dossard", "Nom", "Course", "Section", "Progression",
                                              "Classements"]),
                    'grimpeurs': (self.get_climbers_data,
                                  ["Position", "Dossard", "Nom", "Course", "D+ total", "Temps", "Vitesse", "Pente moy.",
                                   "Tendance"]),
                    'descendeurs': (self.get_descenders_data,
                                    ["Position", "Dossard", "Nom", "Course", "D- total", "Temps", "Vitesse",
                                     "Pente moy.", "Tendance"]),
                    'vitesse_moyenne': (self.get_speed_avg_data,
                                        ["Position", "Dossard", "Nom", "Course", "Vitesse moyenne"]),
                    'vitesse_effort': (self.get_speed_effort_data,
                                       ["Position", "Dossard", "Nom", "Course", "Vitesse effort"]),
                    'vitesse_sections': (self.get_speed_sections_data,
                                         ["Position", "Dossard", "Nom", "Course", "Section", "Distance", "Vitesse"])
                }

                for analysis_type, (data_func, headers) in analysis_types.items():
                    # Construire le nom du fichier
                    if course == "Toutes les courses":
                        filename = f"{analysis_type}.html"
                    else:
                        filename = f"{analysis_type}_{normalized_course}.html"

                    # Récupérer et formater les données
                    data = data_func(course)

                    # Générer le HTML
                    html = self.create_analysis_table_html(
                        analysis_type.replace('_', ' ').title(),
                        headers,
                        data,
                        course
                    )

                    # Sauvegarder le fichier
                    filepath = os.path.join(analysis_dir, filename)
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(html)

            # Créer l'index des analyses
            index_html = self.create_analyses_index_html(courses)
            with open(os.path.join(analysis_dir, "index.html"), "w", encoding='utf-8') as f:
                f.write(index_html)

            return analysis_dir

        except Exception as e:
            print(f"Erreur lors de l'export des analyses: {str(e)}")
            traceback.print_exc()
            return None

    def create_main_analysis_html(self, timestamp, courses):
        """Créer la page principale avec les liens vers toutes les analyses"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Analyses TOP - Grand Raid</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                .analysis-card {{
                    transition: transform 0.2s;
                }}
                .analysis-card:hover {{
                    transform: translateY(-5px);
                }}
                .course-section {{
                    margin-bottom: 2rem;
                    padding: 1rem;
                    background-color: #f8f9fa;
                    border-radius: 8px;
                }}
            </style>
        </head>
        <body class="bg-light">
            <div class="container py-5">
                <h1 class="text-center mb-5">Analyses TOP - Grand Raid</h1>
        """

        # Ajouter une section pour chaque course
        for course in courses:
            course_folder = course.lower().replace(" ", "_")
            html += f"""
                <div class="course-section">
                    <h2 class="mb-4">{course}</h2>
                    <div class="row g-4">
                        <!-- Progression -->
                        <div class="col-md-6 col-lg-3">
                            <div class="card h-100 shadow analysis-card">
                                <div class="card-body">
                                    <h5 class="card-title">Progression</h5>
                                    <ul class="list-unstyled">
                                        <li><a href="{course_folder}/progression_globale.html" class="text-decoration-none">Progression globale</a></li>
                                        <li><a href="{course_folder}/progression_sections.html" class="text-decoration-none">Progression entre points</a></li>
                                    </ul>
                                </div>
                            </div>
                        </div>

                        <!-- Dénivelés -->
                        <div class="col-md-6 col-lg-3">
                            <div class="card h-100 shadow analysis-card">
                                <div class="card-body">
                                    <h5 class="card-title">Dénivelés</h5>
                                    <ul class="list-unstyled">
                                        <li><a href="{course_folder}/grimpeurs.html" class="text-decoration-none">Top Grimpeurs</a></li>
                                        <li><a href="{course_folder}/descendeurs.html" class="text-decoration-none">Top Descendeurs</a></li>
                                    </ul>
                                </div>
                            </div>
                        </div>

                        <!-- Vitesses -->
                        <div class="col-md-6 col-lg-3">
                            <div class="card h-100 shadow analysis-card">
                                <div class="card-body">
                                    <h5 class="card-title">Vitesses</h5>
                                    <ul class="list-unstyled">
                                        <li><a href="{course_folder}/vitesse_moyenne.html" class="text-decoration-none">Vitesse moyenne</a></li>
                                        <li><a href="{course_folder}/vitesse_effort.html" class="text-decoration-none">Vitesse effort</a></li>
                                        <li><a href="{course_folder}/vitesse_sections.html" class="text-decoration-none">Vitesse par section</a></li>
                                    </ul>
                                </div>
                            </div>
                        </div>

                        <!-- Sections -->
                        <div class="col-md-6 col-lg-3">
                            <div class="card h-100 shadow analysis-card">
                                <div class="card-body">
                                    <h5 class="card-title">Sections</h5>
                                    <ul class="list-unstyled">
                                        <li><a href="{course_folder}/analyse_sections.html" class="text-decoration-none">Analyse par section</a></li>
                                    </ul>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            """

        html += """
                </div>
            </body>
            </html>
            """
        return html

    def get_progression_global_data(self, selected_race="Toutes les courses"):
        """Récupérer les données du tableau de progression globale"""
        global_progressions = []

        for bib in self.bibs:
            if str(bib) in self.scraper.all_data:
                data = self.scraper.all_data[str(bib)]

                # Vérifier la course si un filtre est appliqué
                if selected_race != "Toutes les courses" and data['infos']['race_name'] != selected_race:
                    continue

                checkpoints = data['checkpoints']
                if len(checkpoints) >= 2:
                    first_rank = None
                    last_rank = None

                    # Trouver le premier classement non-nul
                    for cp in checkpoints:
                        if cp['rank']:
                            try:
                                rank = int(cp['rank'])
                                if first_rank is None:
                                    first_rank = rank
                            except ValueError:
                                continue

                    # Trouver le dernier classement non-nul
                    for cp in reversed(checkpoints):
                        if cp['rank']:
                            try:
                                rank = int(cp['rank'])
                                last_rank = rank
                                break
                            except ValueError:
                                continue

                    if first_rank is not None and last_rank is not None:
                        progression = first_rank - last_rank
                        global_progressions.append({
                            'bib': bib,
                            'name': data['infos']['name'],
                            'race': data['infos']['race_name'],
                            'start_pos': first_rank,
                            'end_pos': last_rank,
                            'progression': progression
                        })

        # Trier par progression
        global_progressions.sort(key=lambda x: x['progression'], reverse=True)
        return global_progressions[:20]

    def get_progression_sections_data(self, selected_race="Toutes les courses"):
        """Récupérer les données du tableau de progression par sections avec correction"""
        section_progressions = []

        for bib in self.bibs:
            if str(bib) not in self.scraper.all_data:
                continue

            data = self.scraper.all_data[str(bib)]
            if selected_race != "Toutes les courses" and data['infos']['race_name'] != selected_race:
                continue

            checkpoints = data['checkpoints']

            for i in range(len(checkpoints) - 1):
                try:
                    # Vérifier que les deux points ont des classements valides
                    if (checkpoints[i]['rank'] is not None and
                            checkpoints[i + 1]['rank'] is not None and
                            checkpoints[i]['rank'] != "" and
                            checkpoints[i + 1]['rank'] != ""):

                        rank1 = int(checkpoints[i]['rank'])
                        rank2 = int(checkpoints[i + 1]['rank'])
                        progression = rank1 - rank2  # Valeur positive = amélioration

                        if progression > 0:  # Ne garder que les progressions positives
                            section_progressions.append({
                                'progression': progression,
                                'bib': bib,
                                'name': data['infos']['name'],
                                'race': data['infos']['race_name'],
                                'section': f"{checkpoints[i]['point']} → {checkpoints[i + 1]['point']}",
                                'ranks': f"{rank1} → {rank2}"
                            })
                except (ValueError, TypeError) as e:
                    continue

        # Trier par progression décroissante
        section_progressions.sort(key=lambda x: x['progression'], reverse=True)

        # Convertir en format de données attendu
        formatted_data = []
        for i, prog in enumerate(section_progressions[:20]):
            formatted_data.append([
                i + 1,  # Position
                prog['bib'],  # Dossard
                prog['name'],  # Nom
                prog['race'],  # Course
                prog['section'],  # Section
                f"+{prog['progression']}",  # Progression
                prog['ranks']  # Classements
            ])

        return formatted_data

    def export_progression_analysis(self, export_dir, selected_race):
        try:
            # Progression globale
            raw_data = self.get_progression_global_data(selected_race)

            # Convertir les données du format dictionnaire en liste
            formatted_data = [
                [
                    i + 1,  # Position
                    prog['bib'],  # Dossard
                    prog['name'],  # Nom
                    prog['race'],  # Course
                    prog['start_pos'],  # Position de départ
                    prog['end_pos'],  # Position finale
                    f"+{prog['progression']}" if prog['progression'] > 0 else str(prog['progression'])  # Progression
                ]
                for i, prog in enumerate(raw_data)
            ]

            html = self.create_analysis_table_html(
                "Progression globale",
                ["Position", "Dossard", "Nom", "Course", "Pos. départ", "Pos. finale", "Progression"],
                formatted_data,
                selected_race
            )
            filename = f"progression_globale{'_' + selected_race.lower().replace(' ', '_') if selected_race != 'Toutes les courses' else ''}.html"
            with open(os.path.join(export_dir, filename), "w", encoding="utf-8") as f:
                f.write(html)
            print(f"Successfully exported progression_globale for {selected_race}")

            # Export de la progression par sections
            section_data = self.get_progression_sections_data(selected_race)
            if section_data:  # Vérifier que nous avons des données
                section_html = self.create_analysis_table_html(
                    "Progression entre points",
                    ["Position", "Dossard", "Nom", "Course", "Section", "Progression", "Classements"],
                    section_data,
                    selected_race
                )
                section_filename = f"progression_sections{'_' + selected_race.lower().replace(' ', '_') if selected_race != 'Toutes les courses' else ''}.html"
                with open(os.path.join(export_dir, section_filename), "w", encoding="utf-8") as f:
                    f.write(section_html)
                print(f"Successfully exported progression_sections for {selected_race}")

        except Exception as e:
            print(f"Error during export of progression analysis: {str(e)}")
            traceback.print_exc()

    def export_elevation_analysis(self, export_dir, selected_race):
        try:
            # Grimpeurs
            data = self.get_climbers_data(selected_race)
            html = self.create_analysis_table_html(
                "Top Grimpeurs",
                ["Position", "Dossard", "Nom", "Course", "D+ total", "Temps", "Vitesse", "Pente moy.", "Tendance"],
                data,
                selected_race
            )
            filename = f"grimpeurs{'_' + selected_race.lower().replace(' ', '_') if selected_race != 'Toutes les courses' else ''}.html"
            with open(os.path.join(export_dir, filename), "w", encoding="utf-8") as f:
                f.write(html)
            print(f"Successfully exported grimpeurs for {selected_race}")

            # Descendeurs
            data = self.get_descenders_data(selected_race)
            html = self.create_analysis_table_html(
                "Top Descendeurs",
                ["Position", "Dossard", "Nom", "Course", "D- total", "Temps", "Vitesse", "Pente moy.", "Tendance"],
                data,
                selected_race
            )
            filename = f"descendeurs{'_' + selected_race.lower().replace(' ', '_') if selected_race != 'Toutes les courses' else ''}.html"
            with open(os.path.join(export_dir, filename), "w", encoding="utf-8") as f:
                f.write(html)
            print(f"Successfully exported descendeurs for {selected_race}")
        except Exception as e:
            print(f"Error during export of elevation analysis: {str(e)}")
            traceback.print_exc()

    def export_speed_analysis(self, export_dir, selected_race):
        try:
            # Vitesse moyenne
            data = self.get_speed_avg_data(selected_race)
            html = self.create_analysis_table_html(
                "Vitesse moyenne",
                ["Position", "Dossard", "Nom", "Course", "Vitesse moyenne"],
                data,
                selected_race
            )
            filename = f"vitesse_moyenne{'_' + selected_race.lower().replace(' ', '_') if selected_race != 'Toutes les courses' else ''}.html"
            with open(os.path.join(export_dir, filename), "w", encoding="utf-8") as f:
                f.write(html)
            print(f"Successfully exported vitesse_moyenne for {selected_race}")

            # Vitesse effort
            data = self.get_speed_effort_data(selected_race)
            html = self.create_analysis_table_html(
                "Vitesse effort",
                ["Position", "Dossard", "Nom", "Course", "Vitesse effort"],
                data,
                selected_race
            )
            filename = f"vitesse_effort{'_' + selected_race.lower().replace(' ', '_') if selected_race != 'Toutes les courses' else ''}.html"
            with open(os.path.join(export_dir, filename), "w", encoding="utf-8") as f:
                f.write(html)
            print(f"Successfully exported vitesse_effort for {selected_race}")

            # Vitesse par section
            data = self.get_speed_sections_data(selected_race)
            html = self.create_analysis_table_html(
                "Vitesse par section",
                ["Position", "Dossard", "Nom", "Course", "Section", "Distance", "Vitesse"],
                data,
                selected_race
            )
            filename = f"vitesse_sections{'_' + selected_race.lower().replace(' ', '_') if selected_race != 'Toutes les courses' else ''}.html"
            with open(os.path.join(export_dir, filename), "w", encoding="utf-8") as f:
                f.write(html)
            print(f"Successfully exported vitesse_sections for {selected_race}")
        except Exception as e:
            print(f"Error during export of speed analysis: {str(e)}")
            traceback.print_exc()


    def export_section_analysis(self, export_dir):
        """Exporter l'analyse des sections"""
        try:
            # Récupérer toutes les courses
            courses = ["Toutes les courses"] + sorted(list(set(
                data['infos']['race_name']
                for bib in self.bibs
                if str(bib) in self.scraper.all_data
                for data in [self.scraper.all_data[str(bib)]]
            )))

            # Générer le HTML avec les données préchargées
            html = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>Analyse par sections</title>
                <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
                <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
                <script src="https://cdn.datatables.net/1.10.24/js/jquery.dataTables.min.js"></script>
                <script src="https://cdn.datatables.net/1.10.24/js/dataTables.bootstrap5.min.js"></script>
                <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.10.24/css/dataTables.bootstrap5.min.css">
                <style>
                    .section-card { 
                        margin-bottom: 1rem; 
                        border: 1px solid #dee2e6;
                        border-radius: 0.25rem;
                    }
                    .section-header {
                        padding: 1rem;
                        background-color: #f8f9fa;
                        cursor: pointer;
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                    }
                    .section-content {
                        display: none;
                        padding: 1rem;
                    }
                    .performance-section { margin-top: 1rem; }
                    .toggle-icon { font-size: 1.2rem; }
                    .section-info {
                        display: flex;
                        gap: 2rem;
                        color: #666;
                        margin: 1rem 0;
                    }
                </style>
            </head>
            <body>
                <div class="container py-4">
                    <h1>Analyse par sections</h1>
                    <div class="mb-4">
                        <a href="index.html" class="btn btn-secondary">← Retour au menu</a>
                    </div>

                    <div class="mb-3">
                        <label for="courseSelect" class="form-label">Sélectionner une course:</label>
                        <select id="courseSelect" class="form-select" style="width: auto;">
            """

            # Ajouter les options de course
            for course in courses:
                html += f'<option value="{course}">{course}</option>'

            html += """
                        </select>
                    </div>
            """

            # Pour chaque course, préchoarger et ajouter les données
            for course in courses:
                section_data = self.preload_section_data(course)

                html += f"""
                    <div class="course-sections" id="sections-{course.lower().replace(' ', '-')}">
                """

                for section_name, data in section_data.items():
                    html += f"""
                        <div class="section-card">
                            <div class="section-header" onclick="toggleSection(this)">
                                <h3 class="mb-0">{section_name}</h3>
                                <span class="toggle-icon">▼</span>
                            </div>
                            <div class="section-content">
                                <div class="section-info">
                                    <div>Distance: {data['info']['distance']:.1f} km</div>
                                    <div>D+: {data['info']['elevation_gain']} m</div>
                                    <div>D-: {data['info']['elevation_loss']} m</div>
                                </div>

                                <div class="performance-section">
                                    <h4>Top temps</h4>
                                    {self.create_section_table_html(
                        data['temps'],
                        ["Position", "Dossard", "Nom", "Course", "Temps", "Vitesse"],
                        f"temps-{section_name.lower().replace(' ', '-')}"
                    )}
                                </div>

                                <div class="performance-section">
                                    <h4>Top progressions</h4>
                                    {self.create_section_table_html(
                        data['progression'],
                        ["Position", "Dossard", "Nom", "Course", "Progression", "Évolution"],
                        f"progression-{section_name.lower().replace(' ', '-')}"
                    )}
                                </div>
                            </div>
                        </div>
                    """

                html += "</div>"

            html += """
                    <script>
                        function toggleSection(header) {
                            const content = header.nextElementSibling;
                            const icon = header.querySelector('.toggle-icon');

                            if (content.style.display === 'none' || !content.style.display) {
                                content.style.display = 'block';
                                icon.textContent = '▲';
                            } else {
                                content.style.display = 'none';
                                icon.textContent = '▼';
                            }
                        }

                        $(document).ready(function() {
                            // Cacher toutes les sections sauf la première course
                            $('.course-sections').hide();
                            $('.course-sections').first().show();

                            // Gérer le changement de course
                            $('#courseSelect').change(function() {
                                let selectedCourse = $(this).val().replace(/ +/g, '-').toLowerCase();
                                $('.course-sections').hide();
                                $('#sections-' + selectedCourse).show();
                            });
                        });
                    </script>
                </div>
            </body>
            </html>
            """

            # Sauvegarder le fichier
            with open(os.path.join(export_dir, "analyse_sections.html"), "w", encoding="utf-8") as f:
                f.write(html)

        except Exception as e:
            print(f"Erreur lors de l'export de l'analyse des sections: {str(e)}")
            traceback.print_exc()

    def create_analysis_table_html(self, title, headers, data, selected_race):
        """Créer la page HTML d'analyse avec navigation et filtrage corrects"""
        # Récupérer la liste complète des courses
        courses = self.get_unique_races()

        # Fonction pour générer les liens
        def get_page_link(base_name, course):
            if course == "Toutes les courses":
                return f"{base_name}.html"
            return f"{base_name}_{course.lower().replace(' ', '_')}.html"

        # Structure de navigation
        nav_pages = {
            "Progression": [
                ("progression_globale", "Progression globale"),
                ("progression_sections", "Progression entre points")
            ],
            "Dénivelés": [
                ("grimpeurs", "Top Grimpeurs"),
                ("descendeurs", "Top Descendeurs")
            ],
            "Vitesses": [
                ("vitesse_moyenne", "Vitesse moyenne"),
                ("vitesse_effort", "Vitesse effort"),
                ("vitesse_sections", "Vitesse par section")
            ]
        }

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>{title}</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
            <script src="https://cdn.datatables.net/1.10.24/js/jquery.dataTables.min.js"></script>
            <script src="https://cdn.datatables.net/1.10.24/js/dataTables.bootstrap5.min.js"></script>
            <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.10.24/css/dataTables.bootstrap5.min.css">
            <style>
                .progression-positive {{ color: green; }}
                .progression-negative {{ color: red; }}
                .sticky-controls {{
                    position: sticky;
                    top: 0;
                    background: white;
                    padding: 1rem 0;
                    z-index: 1000;
                    border-bottom: 1px solid #dee2e6;
                }}
                .nav-section {{
                    border-bottom: 1px solid #dee2e6;
                    margin-bottom: 1rem;
                }}
                .nav-section a {{
                    color: #6c757d;
                    text-decoration: none;
                    padding: 0.5rem 1rem;
                    display: inline-block;
                }}
                .nav-section a:hover {{
                    color: #0d6efd;
                }}
                .nav-section .active {{
                    color: #0d6efd;
                    border-bottom: 2px solid #0d6efd;
                }}
            </style>
        </head>
        <body>
            <div class="container-fluid">
                <div class="sticky-controls">
                    <div class="row align-items-center">
                        <div class="col-auto">
                            <a href="index.html" class="btn btn-secondary">← Retour au menu</a>
                        </div>
                        <div class="col">
                            <h2 class="mb-0">{title}</h2>
                        </div>
                        <div class="col-auto">
                            <select id="courseSelect" class="form-select" onchange="changeCourse(this.value)">
        """

        # Générer les options du sélecteur
        for course in courses:
            selected = "selected" if course == selected_race else ""
            html += f'<option value="{course}" {selected}>{course}</option>'

        html += """
                            </select>
                        </div>
                    </div>
                </div>

                <div class="nav-section">
                    <div class="container-fluid">
                        <div class="row">
        """

        # Générer la navigation
        for section_title, pages in nav_pages.items():
            html += f"""
                            <div class="col">
                                <h4>{section_title}</h4>
            """
            for page_id, page_name in pages:
                is_active = page_id in title.lower()
                link = get_page_link(page_id, selected_race)
                html += f'<a href="{link}" class="{"active" if is_active else ""}">{page_name}</a>'
            html += """
                            </div>
            """

        html += """
                        </div>
                    </div>
                </div>

                <table id="analysisTable" class="table table-striped">
                    <thead>
                        <tr>
        """

        # Ajouter les en-têtes du tableau
        for header in headers:
            html += f"<th>{header}</th>"

        html += """
                        </tr>
                    </thead>
                    <tbody>
        """

        # Ajouter les données du tableau
        for row in data:
            html += "<tr>"
            for cell in row:
                html += f"<td>{cell}</td>"
            html += "</tr>"

        html += """
                    </tbody>
                </table>
            </div>
            <script>
                function changeCourse(course) {
                    const currentPath = window.location.pathname;
                    const basePath = currentPath.split('/').slice(0, -1).join('/');
                    const currentFile = currentPath.split('/').pop();

                    const pageTypes = {
                        'vitesse_moyenne': 'vitesse_moyenne',
                        'vitesse_effort': 'vitesse_effort',
                        'vitesse_sections': 'vitesse_sections',
                        'progression_globale': 'progression_globale',
                        'progression_sections': 'progression_sections',
                        'grimpeurs': 'grimpeurs',
                        'descendeurs': 'descendeurs'
                    };

                    let pageType = '';
                    for (const type in pageTypes) {
                        if (currentFile.startsWith(type)) {
                            pageType = type;
                            break;
                        }
                    }

                    if (!pageType) {
                        console.error('Type de page non reconnu:', currentFile);
                        return;
                    }

                    let newPage;
                    if (course === "Toutes les courses") {
                        newPage = `${pageType}.html`;
                    } else {
                        const normalizedCourse = course.toLowerCase()
                            .replace(/ /g, '_')
                            .normalize('NFD')
                            .replace(/[\u0300-\u036f]/g, '');
                        newPage = `${pageType}_${normalizedCourse}.html`;
                    }

                    window.location.href = `${basePath}/${newPage}`;
                }

                $(document).ready(function() {
                    const table = $('#analysisTable').DataTable({
                        "pageLength": 20,
                        "lengthMenu": [20],
                        "language": {
                            "url": "//cdn.datatables.net/plug-ins/1.10.24/i18n/French.json"
                        },
                        "order": [[0, "asc"]],
                        "dom": 'rt<"bottom"ip>'
                    });
                });
            </script>
        </body>
        </html>
        """

        return html

    def format_data_row(self, row):
        """Formater une ligne de données pour l'affichage HTML"""
        html = "<tr>"
        for value in row:
            # Formatter les progressions avec des couleurs
            if isinstance(value, (int, float)) and "++" not in str(value):
                try:
                    num_value = float(str(value).replace('+', ''))
                    if num_value > 0:
                        html += f'<td class="progression-positive">+{value}</td>'
                    elif num_value < 0:
                        html += f'<td class="progression-negative">{value}</td>'
                    else:
                        html += f"<td>{value}</td>"
                except ValueError:
                    html += f"<td>{value}</td>"
            else:
                html += f"<td>{value}</td>"
        html += "</tr>"
        return html

    def get_course_options(self):
        """Générer les options HTML pour le menu déroulant des courses"""
        races = set()
        for bib in self.scraper.all_data:
            race = self.scraper.all_data[bib]['infos']['race_name']
            races.add(race)

        options = ""
        for race in sorted(races):
            options += f'<option value="{race}">{race}</option>'
        return options

    def create_course_tables(self, headers, data):
        """Créer des tableaux HTML séparés pour chaque course"""
        races = {"all": data}  # Toutes les courses

        # Séparer les données par course
        for row in data:
            race = row[3]  # Index de la colonne course
            if race not in races:
                races[race] = []
            races[race].append(row)

        # Créer un tableau pour chaque course
        tables = ""
        for race, race_data in races.items():
            race_id = race.replace(" ", "-")
            display = "block" if race == "all" else "none"

            tables += f"""
            <div id="table-{race_id}" class="course-table" style="display: {display}">
                <table class="table">
                    <thead>
                        <tr>{''.join(f'<th>{h}</th>' for h in headers)}</tr>
                    </thead>
                    <tbody>
                        {''.join(f'<tr>{"".join(f"<td>{cell}</td>" for cell in row)}</tr>' for row in race_data)}
                    </tbody>
                </table>
            </div>
            """
        return tables

    def calculate_climbing_speed(self, elevation_gain, time_str, distance):
        """
        Calcule la vitesse verticale en montée
        Args:
            elevation_gain: dénivelé en mètres
            time_str: temps au format HH:MM:SS
            distance: distance horizontale en km
        Returns:
            tuple: (vitesse verticale en m/h, pente moyenne en %)
        """
        try:
            # Convertir le temps HH:MM:SS en heures
            h, m, s = map(int, time_str.split(':'))
            time_hours = h + m / 60 + s / 3600

            if time_hours == 0:
                return 0, 0

            # Calcul de la vitesse verticale
            vertical_speed = elevation_gain / time_hours  # m/h

            # Calcul de la pente moyenne
            distance_m = distance * 1000  # conversion km en m
            if distance_m > 0:
                slope_percentage = (elevation_gain / distance_m) * 100
            else:
                slope_percentage = 0

            return vertical_speed, slope_percentage

        except Exception as e:
            print(f"Erreur dans le calcul de vitesse verticale: {str(e)}")
            return 0, 0

    def get_climbers_data(self, selected_race="Toutes les courses"):
        """Version corrigée de l'analyse des grimpeurs"""
        climbers = []

        for bib in self.bibs:
            if str(bib) not in self.scraper.all_data:
                continue

            data = self.scraper.all_data[str(bib)]
            if selected_race != "Toutes les courses" and data['infos']['race_name'] != selected_race:
                continue

            checkpoints = data['checkpoints']

            for i in range(len(checkpoints) - 1):
                if checkpoints[i + 1]['elevation_gain'] > 100:  # On regarde le D+ du point suivant
                    try:
                        # Le D+ est celui du point d'arrivée
                        elevation_gain = checkpoints[i + 1]['elevation_gain']

                        # Le temps est calculé entre les deux points
                        section_time = self.time_diff(
                            checkpoints[i + 1]['race_time'],
                            checkpoints[i]['race_time']
                        )

                        if not section_time:
                            continue

                        # Distance entre les deux points
                        distance = checkpoints[i + 1]['kilometer'] - checkpoints[i]['kilometer']

                        # Calcul du temps en heures pour la vitesse
                        h, m, s = map(int, section_time.split(':'))
                        time_hours = h + m / 60 + s / 3600

                        if time_hours > 0:
                            # Vitesse verticale en m/h
                            vertical_speed = elevation_gain / time_hours

                            # Pente moyenne en %
                            slope_percentage = (elevation_gain / (distance * 1000)) * 100 if distance > 0 else 0

                            section_name = f"{checkpoints[i]['point']} → {checkpoints[i + 1]['point']}"

                            climbers.append({
                                'bib': bib,
                                'name': data['infos']['name'],
                                'race': data['infos']['race_name'],
                                'elevation_gain': elevation_gain,
                                'time_hours': time_hours,
                                'time': section_time,
                                'speed': vertical_speed,
                                'slope': slope_percentage,
                                'section': section_name,
                                'distance': distance
                            })

                    except Exception as e:
                        print(f"Erreur calcul grimpeur dossard {bib}: {str(e)}")
                        continue

        # Trier par vitesse verticale
        climbers.sort(key=lambda x: x['speed'], reverse=True)

        # Formater les données pour l'affichage
        formatted_data = []
        for i, climb in enumerate(climbers[:20]):
            formatted_data.append([
                i + 1,
                climb['bib'],
                climb['name'],
                climb['race'],
                f"{climb['elevation_gain']}m",
                climb['time'],
                f"{climb['speed']:.1f} m/h",
                f"{climb['slope']:.1f}%",
                f"{climb['section']}"
            ])

        return formatted_data

    def get_descenders_data(self, selected_race="Toutes les courses"):
        """Version corrigée de l'analyse des descendeurs"""
        descenders = []

        for bib in self.bibs:
            if str(bib) not in self.scraper.all_data:
                continue

            data = self.scraper.all_data[str(bib)]
            if selected_race != "Toutes les courses" and data['infos']['race_name'] != selected_race:
                continue

            checkpoints = data['checkpoints']

            for i in range(len(checkpoints) - 1):
                if checkpoints[i + 1]['elevation_loss'] > 100:  # On regarde le D- du point suivant
                    try:
                        # Le D- est celui du point d'arrivée
                        elevation_loss = checkpoints[i + 1]['elevation_loss']

                        # Le temps est calculé entre les deux points
                        section_time = self.time_diff(
                            checkpoints[i + 1]['race_time'],
                            checkpoints[i]['race_time']
                        )

                        if not section_time:
                            continue

                        # Distance entre les deux points
                        distance = checkpoints[i + 1]['kilometer'] - checkpoints[i]['kilometer']

                        # Calcul du temps en heures pour la vitesse
                        h, m, s = map(int, section_time.split(':'))
                        time_hours = h + m / 60 + s / 3600

                        if time_hours > 0:
                            # Vitesse verticale en m/h
                            vertical_speed = elevation_loss / time_hours

                            # Pente moyenne en %
                            slope_percentage = (elevation_loss / (distance * 1000)) * 100 if distance > 0 else 0

                            section_name = f"{checkpoints[i]['point']} → {checkpoints[i + 1]['point']}"

                            descenders.append({
                                'bib': bib,
                                'name': data['infos']['name'],
                                'race': data['infos']['race_name'],
                                'elevation_loss': elevation_loss,
                                'time_hours': time_hours,
                                'time': section_time,
                                'speed': vertical_speed,
                                'slope': slope_percentage,
                                'section': section_name,
                                'distance': distance
                            })

                    except Exception as e:
                        print(f"Erreur calcul descendeur dossard {bib}: {str(e)}")
                        continue

        # Trier par vitesse verticale
        descenders.sort(key=lambda x: x['speed'], reverse=True)

        # Formater les données pour l'affichage
        formatted_data = []
        for i, desc in enumerate(descenders[:20]):
            formatted_data.append([
                i + 1,
                desc['bib'],
                desc['name'],
                desc['race'],
                f"{desc['elevation_loss']}m",
                desc['time'],
                f"{desc['speed']:.1f} m/h",
                f"{desc['slope']:.1f}%",
                f"{desc['section']}"
            ])

        return formatted_data

    def get_speed_avg_data(self, selected_race="Toutes les courses"):
        """Récupérer les données des vitesses moyennes en recalculant depuis les données brutes"""
        speeds = []

        for bib in self.bibs:
            if str(bib) in self.scraper.all_data:
                data = self.scraper.all_data[str(bib)]
                if selected_race == "Toutes les courses" or data['infos']['race_name'] == selected_race:
                    checkpoints = data['checkpoints']

                    # Calculer la moyenne des vitesses pour ce coureur
                    valid_speeds = []
                    for cp in checkpoints:
                        try:
                            speed = float(cp['speed'].replace('km/h', '').strip())
                            valid_speeds.append(speed)
                        except:
                            continue

                    if valid_speeds:
                        avg_speed = sum(valid_speeds) / len(valid_speeds)
                        speeds.append({
                            'speed': avg_speed,
                            'bib': bib,
                            'name': data['infos']['name'],
                            'race': data['infos']['race_name']
                        })

        # Trier par vitesse décroissante
        speeds.sort(key=lambda x: x['speed'], reverse=True)

        # Formater pour l'affichage
        return [
            [i + 1, item['bib'], item['name'], item['race'], f"{item['speed']:.1f} km/h"]
            for i, item in enumerate(speeds[:20])
        ]

    def get_speed_effort_data(self, selected_race="Toutes les courses"):
        """Récupérer les données des vitesses effort en recalculant depuis les données brutes"""
        efforts = []

        for bib in self.bibs:
            if str(bib) in self.scraper.all_data:
                data = self.scraper.all_data[str(bib)]
                if selected_race == "Toutes les courses" or data['infos']['race_name'] == selected_race:
                    checkpoints = data['checkpoints']

                    valid_efforts = []
                    for cp in checkpoints:
                        try:
                            effort = float(cp['effort_speed'].replace('km/h', '').strip())
                            valid_efforts.append(effort)
                        except:
                            continue

                    if valid_efforts:
                        avg_effort = sum(valid_efforts) / len(valid_efforts)
                        efforts.append({
                            'effort': avg_effort,
                            'bib': bib,
                            'name': data['infos']['name'],
                            'race': data['infos']['race_name']
                        })

        # Trier par vitesse effort décroissante
        efforts.sort(key=lambda x: x['effort'], reverse=True)

        # Formater pour l'affichage
        return [
            [i + 1, item['bib'], item['name'], item['race'], f"{item['effort']:.1f} km/h"]
            for i, item in enumerate(efforts[:20])
        ]

    def get_speed_sections_data(self, selected_race="Toutes les courses"):
        """Récupérer les données des vitesses par section en recalculant depuis les données brutes"""
        section_speeds = []

        for bib in self.bibs:
            if str(bib) in self.scraper.all_data:
                data = self.scraper.all_data[str(bib)]
                if selected_race == "Toutes les courses" or data['infos']['race_name'] == selected_race:
                    checkpoints = data['checkpoints']

                    for i in range(len(checkpoints) - 1):
                        try:
                            section_time = self.time_diff(
                                checkpoints[i + 1]['race_time'],
                                checkpoints[i]['race_time']
                            )

                            if section_time:
                                h, m, s = map(int, section_time.split(':'))
                                hours = h + m / 60 + s / 3600
                                distance = checkpoints[i + 1]['kilometer'] - checkpoints[i]['kilometer']

                                if hours > 0:
                                    speed = distance / hours
                                    section_speeds.append({
                                        'speed': speed,
                                        'bib': bib,
                                        'name': data['infos']['name'],
                                        'race': data['infos']['race_name'],
                                        'from_point': checkpoints[i]['point'],
                                        'to_point': checkpoints[i + 1]['point'],
                                        'distance': distance
                                    })
                        except Exception as e:
                            print(f"Erreur calcul vitesse section {i} pour dossard {bib}: {e}")
                            continue

        # Trier par vitesse décroissante
        section_speeds.sort(key=lambda x: x['speed'], reverse=True)

        # Formater pour l'affichage
        return [
            [i + 1, item['bib'], item['name'], item['race'],
             f"{item['from_point']} → {item['to_point']}",
             f"{item['distance']:.1f} km",
             f"{item['speed']:.1f} km/h"]
            for i, item in enumerate(section_speeds[:20])
        ]

    def get_section_time_data(self):
        """Récupérer les données de temps pour la section sélectionnée"""
        try:
            data = []
            for widget in self.section_results_scroll.winfo_children():
                if isinstance(widget, ttk.Treeview) and widget.winfo_ismapped():
                    for item in widget.get_children():
                        values = widget.item(item)['values']
                        if values and len(values) >= 6:
                            data.append([
                                values[0],  # Position
                                values[1],  # Dossard
                                values[2],  # Nom
                                values[3],  # Course
                                values[4],  # Temps
                                values[5]  # Tendance
                            ])
                    break
            return data
        except Exception as e:
            print(f"Erreur lors de la récupération des données de temps: {str(e)}")
            return []

    def get_section_speed_data(self):
        """Récupérer les données de vitesse pour la section sélectionnée"""
        try:
            data = []
            for widget in self.section_results_scroll.winfo_children():
                if isinstance(widget, ttk.Treeview) and widget.winfo_ismapped():
                    for item in widget.get_children():
                        values = widget.item(item)['values']
                        if values and len(values) >= 6:
                            data.append([
                                values[0],  # Position
                                values[1],  # Dossard
                                values[2],  # Nom
                                values[3],  # Course
                                values[4],  # Vitesse
                                values[5]  # Tendance
                            ])
                    break
            return data
        except Exception as e:
            print(f"Erreur lors de la récupération des données de vitesse: {str(e)}")
            return []

    def get_section_effort_data(self):
        """Récupérer les données de vitesse effort pour la section sélectionnée"""
        try:
            data = []
            for widget in self.section_results_scroll.winfo_children():
                if isinstance(widget, ttk.Treeview) and widget.winfo_ismapped():
                    for item in widget.get_children():
                        values = widget.item(item)['values']
                        if values and len(values) >= 6:
                            data.append([
                                values[0],  # Position
                                values[1],  # Dossard
                                values[2],  # Nom
                                values[3],  # Course
                                values[4],  # Vitesse effort
                                values[5]  # Tendance
                            ])
                    break
            return data
        except Exception as e:
            print(f"Erreur lors de la récupération des données de vitesse effort: {str(e)}")
            return []

    def get_section_progressions_data(self, selected_race="Toutes les courses"):
        """Récupérer les données du tableau de progression par sections"""
        section_progressions = []

        for bib in self.bibs:
            if str(bib) not in self.scraper.all_data:
                continue

            data = self.scraper.all_data[str(bib)]
            if selected_race != "Toutes les courses" and data['infos']['race_name'] != selected_race:
                continue

            checkpoints = data['checkpoints']

            # Parcourir tous les points consécutifs
            for i in range(len(checkpoints) - 1):
                if checkpoints[i]['rank'] and checkpoints[i + 1]['rank']:
                    try:
                        rank1 = int(checkpoints[i]['rank'])
                        rank2 = int(checkpoints[i + 1]['rank'])
                        progression = rank1 - rank2

                        # Ajouter seulement les progressions positives
                        if progression > 0:
                            section_progressions.append({
                                'bib': bib,
                                'name': data['infos']['name'],
                                'race': data['infos']['race_name'],
                                'section': f"{checkpoints[i]['point']} → {checkpoints[i + 1]['point']}",
                                'progression': progression,
                                'ranks': f"{rank1} → {rank2}"
                            })
                    except (ValueError, TypeError):
                        continue

        # Trier par progression
        section_progressions.sort(key=lambda x: x['progression'], reverse=True)
        return section_progressions[:20]

    def create_section_analysis_html(self):
        """Créer le HTML pour l'analyse des sections avec navigation améliorée"""
        html = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>Analyse des sections</title>
                <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
                <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
                <style>
                    .section-card { transition: all 0.3s ease; }
                    .section-card:hover { transform: translateY(-2px); }

                    .performance-table {
                        width: 100%;
                        margin: 1rem 0;
                    }

                    .nav-pills { margin-bottom: 2rem; }

                    @media print {
                        .no-print { display: none; }
                    }
                </style>
            </head>
            <body>
                <div class="container-fluid p-4">
                    <div class="row">
                        <div class="col">
                            <nav class="navbar navbar-expand-lg no-print">
                                <div class="container-fluid">
                                    <select id="courseFilter" class="form-select me-2">
                                        <!-- Options de courses -->
                                    </select>
                                    <button class="btn btn-outline-secondary" onclick="window.print()">
                                        Imprimer
                                    </button>
                                </div>
                            </nav>
                        </div>
                    </div>

                    <div class="section-container mt-4">
                        <!-- Contenu des sections -->
                    </div>
                </div>

                <script>
                    // Amélioration de la navigation
                    $(document).ready(function() {
                        // Mémorisation du filtre
                        $('#courseFilter').change(function() {
                            localStorage.setItem('selectedCourse', $(this).val());
                            filterSections();
                        });

                        // Restore du dernier filtre
                        let lastFilter = localStorage.getItem('selectedCourse');
                        if (lastFilter) {
                            $('#courseFilter').val(lastFilter);
                            filterSections();
                        }
                    });

                    function filterSections() {
                        const course = $('#courseFilter').val();
                        $('.section-card').each(function() {
                            const sectionCourse = $(this).data('course');
                            $(this).toggle(course === 'all' || sectionCourse === course);
                        });
                    }
                </script>
            </body>
            </html>
        """
        return html

    def create_section_table_html(self, data, headers, table_id=None):
        """Créer un tableau HTML pour une section"""
        if not data:
            return "<div class='alert alert-info'>Aucune donnée disponible pour cette section</div>"

        table_id = table_id or f"table-{hash(str(headers))}"

        html = f"""
            <div class="table-responsive">
                <table id="{table_id}" class="table table-striped">
                    <thead>
                        <tr>
                            {"".join(f"<th>{header}</th>" for header in headers)}
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(self.format_data_row(row) for row in data)}
                    </tbody>
                </table>
            </div>

            <script>
                (function() {{
                    if (!$.fn.DataTable.isDataTable('#{table_id}')) {{
                        const table = $('#{table_id}').DataTable({{
                            "pageLength": 20,
                            "lengthMenu": [20],
                            "language": {{
                                "url": "//cdn.datatables.net/plug-ins/1.10.24/i18n/French.json"
                            }},
                            "order": [],
                            "dom": 'frt<"bottom"ip>',
                            "searching": true,
                            "info": true,
                            "paginate": true
                        }});

                        $('#courseSelect').change(function() {{
                            const selectedCourse = $(this).val();
                            table.column(3).search(selectedCourse === 'all' ? '' : selectedCourse, true, false).draw();
                        }});
                    }}
                }})();
            </script>
        """
        return html

    def get_section_performances(self, section_name, selected_race):
        """Récupérer toutes les performances pour une section donnée"""
        times = []
        progressions = []
        speeds = []

        try:
            for bib in self.bibs:
                if str(bib) not in self.scraper.all_data:
                    continue

                runner_data = self.scraper.all_data[str(bib)]

                if selected_race != "Toutes les courses" and runner_data['infos']['race_name'] != selected_race:
                    continue

                checkpoints = runner_data['checkpoints']

                for i in range(len(checkpoints) - 1):
                    current_section = f"{checkpoints[i]['point']} → {checkpoints[i + 1]['point']}"
                    if current_section == section_name:
                        try:
                            # Utiliser la nouvelle méthode de calcul de temps
                            section_time = self.time_diff(checkpoints[i + 1]['race_time'],
                                                          checkpoints[i]['race_time'])

                            if section_time is None:
                                continue

                            # Convertir le temps pour le calcul de vitesse
                            h, m, s = map(int, section_time.split(':'))
                            hours = h + m / 60 + s / 3600

                            # Calculer la vitesse si le temps est valide
                            if hours > 0:
                                distance = checkpoints[i + 1]['kilometer'] - checkpoints[i]['kilometer']
                                speed = distance / hours

                                # Calculer vitesse effort
                                d_plus = checkpoints[i]['elevation_gain'] or 0
                                d_minus = checkpoints[i]['elevation_loss'] or 0
                                effort_distance = distance + (d_plus / 1000 * 10) + (d_minus / 1000 * 2)
                                effort_speed = effort_distance / hours

                                # Progression
                                rank1 = int(checkpoints[i]['rank']) if checkpoints[i]['rank'] else 0
                                rank2 = int(checkpoints[i + 1]['rank']) if checkpoints[i + 1]['rank'] else 0
                                progression = rank1 - rank2 if rank1 and rank2 else 0

                                # Ajouter aux listes
                                times.append([
                                    len(times) + 1,
                                    bib,
                                    runner_data['infos']['name'],
                                    runner_data['infos']['race_name'],
                                    section_time,
                                    f"{speed:.1f} km/h"
                                ])

                                progressions.append([
                                    len(progressions) + 1,
                                    bib,
                                    runner_data['infos']['name'],
                                    runner_data['infos']['race_name'],
                                    progression,
                                    f"{rank1} → {rank2}"
                                ])

                                speeds.append([
                                    len(speeds) + 1,
                                    bib,
                                    runner_data['infos']['name'],
                                    runner_data['infos']['race_name'],
                                    f"{speed:.1f} km/h",
                                    f"{effort_speed:.1f} km/h"
                                ])

                        except Exception as e:
                            print(f"Erreur lors du calcul des performances pour le dossard {bib}: {str(e)}")
                        break

            # Trier les listes
            times.sort(key=lambda x: x[4])  # tri par temps
            progressions.sort(key=lambda x: x[4], reverse=True)  # tri par progression
            speeds.sort(key=lambda x: float(x[4].split()[0]), reverse=True)  # tri par vitesse

            # Limiter à TOP 20
            times = times[:20]
            progressions = progressions[:20]
            speeds = speeds[:20]

            # Mettre à jour les positions après le tri
            for i, perf in enumerate(times, 1):
                perf[0] = i
            for i, perf in enumerate(progressions, 1):
                perf[0] = i
            for i, perf in enumerate(speeds, 1):
                perf[0] = i

            return {
                'times': times,
                'progressions': progressions,
                'speeds': speeds
            }

        except Exception as e:
            print(f"Erreur lors de la récupération des performances de la section {section_name}: {str(e)}")
            return {'times': [], 'progressions': [], 'speeds': []}



if __name__ == "__main__":
    app = RaceTrackerApp()
    app.run()